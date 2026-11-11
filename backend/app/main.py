"""FastAPI application. Stateless: nothing is written to disk and no outbound requests are made."""
from __future__ import annotations

import io
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from python_multipart.multipart import MultipartParser, parse_options_header

from ..analysis import EnvironmentOnlyError, analyze_uploads
from ..export import build_workbook, export_filename
from ..models import ExportRequest
from ..parsers import ParseError

log = logging.getLogger("api-security-planner")

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4 MB across ALL uploaded files combined (Vercel body limit is ~4.5 MB)
MULTIPART_OVERHEAD = 128 * 1024
TOO_LARGE_MSG = "The uploaded files are larger than 4 MB in total."
TOO_LARGE_HINT = "Upload a smaller collection (remove saved responses/examples) or split it into parts."
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

app = FastAPI(title="API Security Test Planner", version="1.1.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None)


class ApiProblem(Exception):
    """An error returned to the client as JSON {code, message, hint} (plus `detail` = message for compatibility)."""

    def __init__(self, status: int, code: str, message: str, hint: str = "", extra: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.hint, self.extra = status, code, message, hint, extra or {}


@app.exception_handler(ApiProblem)
async def problem_handler(_request: Request, exc: ApiProblem):
    body = {"code": exc.code, "message": exc.message, "hint": exc.hint, "detail": exc.message, **exc.extra}
    return JSONResponse(status_code=exc.status, content=body)


def too_large() -> ApiProblem:
    return ApiProblem(413, "FILE_TOO_LARGE", TOO_LARGE_MSG, TOO_LARGE_HINT)


async def read_multipart_files(request: Request) -> dict[str, tuple[bytes, str | None]]:
    """Stream-parse a multipart/form-data body into memory (no temp files).

    Returns {"file": (bytes, filename), "environment": (bytes, filename)} for the parts that were sent.
    The 4 MB limit applies to the combined size of the captured files.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD:
        raise too_large()

    ctype, params = parse_options_header(request.headers.get("content-type", ""))
    boundary = params.get(b"boundary")
    if ctype != b"multipart/form-data" or not boundary:
        raise ApiProblem(400, "BAD_REQUEST", "Expected a multipart/form-data upload with a 'file' field.",
                         "Send the collection as the 'file' field and the optional environment as 'environment'.")

    bufs: dict[str, io.BytesIO] = {}
    names: dict[str, str | None] = {}
    st: dict = {"hname": b"", "hvalue": b"", "headers": {}, "target": None, "total": 0}

    def on_part_begin():
        st.update(headers={}, hname=b"", hvalue=b"", target=None)

    def on_header_field(data, start, end):
        st["hname"] += data[start:end]

    def on_header_value(data, start, end):
        st["hvalue"] += data[start:end]

    def on_header_end():
        st["headers"][st["hname"].lower()] = st["hvalue"]
        st["hname"], st["hvalue"] = b"", b""

    def on_headers_finished():
        _, dp = parse_options_header(st["headers"].get(b"content-disposition", b""))
        fname, name = dp.get(b"filename"), dp.get(b"name")
        target = None
        if name == b"environment":
            target = "environment"
        elif (name == b"file" or fname is not None) and "file" not in bufs:
            target = "file"
        if target and target not in bufs:
            bufs[target] = io.BytesIO()
            names[target] = fname.decode("utf-8", "replace") if fname else None
            st["target"] = target

    def on_part_data(data, start, end):
        if st["target"]:
            st["total"] += end - start
            if st["total"] > MAX_UPLOAD_BYTES:
                raise _TooLarge()
            bufs[st["target"]].write(data[start:end])

    parser = MultipartParser(boundary, {
        "on_part_begin": on_part_begin, "on_header_field": on_header_field, "on_header_value": on_header_value,
        "on_header_end": on_header_end, "on_headers_finished": on_headers_finished, "on_part_data": on_part_data,
    })
    received = 0
    try:
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD:
                raise _TooLarge()
            parser.write(chunk)
        parser.finalize()
    except _TooLarge:
        raise too_large() from None
    except ApiProblem:
        raise
    except Exception:  # malformed multipart
        raise ApiProblem(400, "BAD_REQUEST", "The upload could not be read.",
                         "Send the files as multipart/form-data.") from None
    return {k: (b.getvalue(), names[k]) for k, b in bufs.items()}


class _TooLarge(Exception):
    pass


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(request: Request):
    parts = await read_multipart_files(request)
    if not parts:
        raise ApiProblem(400, "NO_FILE", "No file was uploaded.", "Use the form field name 'file' for the collection.")
    try:
        result = analyze_uploads(
            parts["file"][0] if "file" in parts else None, parts["environment"][0] if "environment" in parts else None,
            parts["file"][1] if "file" in parts else None, parts["environment"][1] if "environment" in parts else None)
        return JSONResponse(content=result.model_dump(mode="json"))
    except EnvironmentOnlyError as e:
        # Still 422 (no collection was analyzed) but the environment review is attached so the UI can show it.
        raise ApiProblem(422, e.code, e.message, e.hint, {"analysis": e.result.model_dump(mode="json")}) from None
    except ParseError as e:
        extra = {k: v for k, v in (("line", e.line), ("column", e.column)) if v is not None}
        raise ApiProblem(422, e.code, e.message, e.hint, extra) from None
    except RecursionError:
        raise ApiProblem(422, "INVALID_SYNTAX", "The file is nested too deeply to be processed.") from None
    except Exception:
        log.exception("analysis failed")
        raise ApiProblem(422, "ANALYSIS_FAILED", "The file could not be analyzed.",
                         "Check that it is a valid Postman v2.1 or OpenAPI/Swagger document.") from None


@app.post("/api/export")
def export(req: ExportRequest) -> StreamingResponse:
    data = build_workbook(req.analysis, req.test_case_ids)
    filename = export_filename(req.analysis, req.test_case_ids is not None)
    return StreamingResponse(io.BytesIO(data), media_type=XLSX_MIME, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(data)),
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Cache-Control": "no-store",
    })
