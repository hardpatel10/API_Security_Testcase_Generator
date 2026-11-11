import io
import json
import re
from collections import Counter

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, range_boundaries

from backend.export import build_workbook, export_filename
from backend.export.excel import FIRST_ROW, HEADER_ROW
from backend.generator import analyze_collection
from backend.models import SAFETY_NOTE
from backend.parsers import build_environment, load_document, parse_bytes

CREDIT_URL = "https://www.linkedin.com/in/hard-pansara-22582a288/"
RAW_SECRETS = ["Passw0rd!123", "Sup3rSecret", "dummysignature", "abcd1234efgh5678", "admin123", "Qm7Lp2Xz9RvTa4KcWb8YdNe5HgFu1JsV"]


def load(data: bytes):
    return load_workbook(io.BytesIO(data))


def all_text(ws) -> str:
    return " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


def col_of(ws, header: str) -> int:
    return next(c.column for c in ws[HEADER_ROW] if c.value == header)


# ---- a tiny evaluator for the formulas the Summary uses (LibreOffice/Excel are not available in CI) -----------------
def _range_values(wb, ref: str):
    m = re.match(r"^'?([^'!]+)'?!(\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+)$", ref)
    sheet, cells = m.group(1), m.group(2).replace("$", "")
    c1, r1, c2, r2 = range_boundaries(cells)
    ws = wb[sheet]
    return [ws.cell(row=r, column=c).value for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]


def evaluate(wb, formula: str):
    f = formula.lstrip("=")
    if re.fullmatch(r"\d+", f):
        return int(f)
    m = re.fullmatch(r"COUNTA\((.+)\)", f)
    if m:
        return sum(v not in (None, "") for v in _range_values(wb, m.group(1)))
    m = re.fullmatch(r'COUNTIF\((.+?),"((?:[^"]|"")*)"\)', f)
    if m:
        crit = m.group(2).replace('""', '"')
        vals = _range_values(wb, m.group(1))
        if crit.endswith("*"):
            return sum(isinstance(v, str) and v.startswith(crit[:-1]) for v in vals)
        return sum(v == crit for v in vals)
    m = re.fullmatch(r"ROUND\(SUMPRODUCT\(1/COUNTIF\((.+?),\1\)\),0\)", f)
    if m:
        vals = _range_values(wb, m.group(1))
        return round(sum(1 / vals.count(v) for v in vals))
    raise AssertionError(f"unsupported formula in test evaluator: {formula}")


# ------------------------------------------------------------------------------------------------ layout
@pytest.fixture()
def analysis(postman):
    return analyze_collection(postman)


@pytest.fixture()
def workbook(analysis):
    return load(build_workbook(analysis))


def test_sheet_order_environment_sheet_only_when_present(analysis, postman, env_bytes):
    assert load(build_workbook(analysis)).sheetnames == ["Summary", "Endpoint Test Plan", "Static Findings", "Standards Reference"]
    env = build_environment(load_document(env_bytes))
    with_env = load(build_workbook(analyze_collection(postman, env)))
    assert with_env.sheetnames == ["Summary", "Endpoint Test Plan", "Static Findings", "Environment Findings", "Standards Reference"]


def test_margin_and_sheet_settings_on_every_sheet(postman, env_bytes):
    env = build_environment(load_document(env_bytes))
    wb = load(build_workbook(analyze_collection(postman, env)))
    for ws in wb:
        assert ws["A1"].value is None, ws.title
        assert all(c.value is None for c in ws[1]), f"row 1 not empty on {ws.title}"
        assert all(row[0].value is None for row in ws.iter_rows(min_col=1, max_col=1)), f"column A not empty on {ws.title}"
        assert ws.column_dimensions["A"].width == 2 and ws.row_dimensions[1].height == 10
        assert ws.sheet_view.showGridLines is False
        assert ws.sheet_view.zoomScale == 90
        assert ws.sheet_properties.tabColor is not None
        assert ws["B2"].value, f"{ws.title} content must start at B2"


def test_table_sheets_title_subtitle_and_header_on_row_5(workbook):
    for name in ("Endpoint Test Plan", "Static Findings", "Standards Reference"):
        ws = workbook[name]
        assert ws["B2"].value == name and ws["B2"].font.size == 18 and ws["B2"].font.bold and ws["B2"].font.color.rgb.endswith("1B2A41")
        assert ws["B3"].value and ws["B3"].font.color.rgb.endswith("5F6B7A")
        assert all(ws.cell(row=4, column=c).value is None for c in range(1, 20))
        hdr = ws["B5"]
        assert hdr.value and hdr.fill.fgColor.rgb.endswith("1B2A41") and hdr.font.bold and hdr.font.color.rgb.endswith("FFFFFF")
        assert hdr.alignment.vertical == "center" and hdr.alignment.wrap_text
        assert ws.row_dimensions[5].height == 30
        assert ws.auto_filter.ref.startswith("B5:")
        assert ws.freeze_panes == "C6"


def test_workbook_structure_and_counts(workbook, analysis):
    plan = workbook["Endpoint Test Plan"]
    headers = [c.value for c in plan[HEADER_ROW] if c.value]
    for h in ("Test ID", "Endpoint ID", "Method", "URL", "Auth", "Test to perform", "How to test", "Expected secure result", "Severity", "Status", "Notes"):
        assert h in headers
    assert plan.max_row == len(analysis.test_cases) + HEADER_ROW
    assert workbook["Static Findings"].max_row == len(analysis.findings) + HEADER_ROW
    assert workbook["Standards Reference"].max_row > 40


def test_column_widths_follow_the_spec(workbook):
    plan = workbook["Endpoint Test Plan"]
    w = {h: plan.column_dimensions[get_column_letter(col_of(plan, h))].width for h in
         ("Test ID", "Method", "URL", "Test to perform", "How to test", "Expected secure result", "Severity", "Status", "Notes")}
    assert w == {"Test ID": 12, "Method": 10, "URL": 40, "Test to perform": 34, "How to test": 60, "Expected secure result": 40,
                 "Severity": 12, "Status": 14, "Notes": 30}
    assert plan.column_dimensions[get_column_letter(col_of(plan, "Standard reference (OWASP API / CWE / ASVS / WSTG)"))].width == 30


def test_body_styling_fonts_banding_borders_and_wrap(workbook, analysis):
    plan = workbook["Endpoint Test Plan"]
    r = FIRST_ROW
    test_id, url, test = plan.cell(r, col_of(plan, "Test ID")), plan.cell(r, col_of(plan, "URL")), plan.cell(r, col_of(plan, "Test to perform"))
    assert test_id.font.name == "Consolas" and url.font.name == "Consolas"
    assert test.font.name == "Calibri" and test.font.size == 10
    assert test.alignment.vertical == "top" and test.alignment.wrap_text
    how = plan.cell(r, col_of(plan, "How to test"))
    assert how.value.startswith("1. ") and "\n2. " in how.value
    assert plan.row_dimensions[r].height > 30  # auto-fitted to the numbered steps
    assert test.border.bottom.style == "thin" and test.border.bottom.color.rgb.endswith("C9D1D9")
    assert all(s is None or s.style is None for s in (test.border.left, test.border.right))  # no heavy grid
    eps = [plan.cell(r, col_of(plan, "Endpoint ID")).value for r in range(FIRST_ROW, plan.max_row + 1)]
    starts = [i for i in range(1, len(eps)) if eps[i] != eps[i - 1]]
    assert starts and all(plan.cell(FIRST_ROW + i, 3).border.top.style == "medium" for i in starts)  # group separators
    fills = {plan.cell(FIRST_ROW + i, 3).fill.fgColor.rgb[-6:] for i in range(len(eps))}
    assert "F7F9FB" in fills  # very light banding


def test_standard_reference_is_short_tags(workbook):
    plan = workbook["Endpoint Test Plan"]
    tags = plan.cell(FIRST_ROW, col_of(plan, "Standard reference (OWASP API / CWE / ASVS / WSTG)")).value
    assert re.fullmatch(r"API\d+:2023 \| CWE-\d+.*ASVS V[\d.]+.*", tags)


def test_status_and_notes_are_exported(analysis):
    analysis.test_cases[0].status = "Fail"
    analysis.test_cases[0].notes = "Reproduced on staging"
    analysis.test_cases[1].status = "Pass"
    plan = load(build_workbook(analysis))["Endpoint Test Plan"]
    s, n = col_of(plan, "Status"), col_of(plan, "Notes")
    assert (plan.cell(FIRST_ROW, s).value, plan.cell(FIRST_ROW, n).value) == ("Fail", "Reproduced on staging")
    assert plan.cell(FIRST_ROW + 1, s).value == "Pass"
    assert plan.cell(FIRST_ROW + 2, s).value == "Not Started"


def test_status_dropdown_and_conditional_formats_cover_shifted_ranges(workbook):
    plan = workbook["Endpoint Test Plan"]
    status, sev = get_column_letter(col_of(plan, "Status")), get_column_letter(col_of(plan, "Severity"))
    dvs = plan.data_validations.dataValidation
    assert len(dvs) == 1 and dvs[0].type == "list" and str(dvs[0].sqref) == f"{status}{FIRST_ROW}:{status}1000"
    for v in ("Not Started", "Pass", "Fail", "N/A"):
        assert v in dvs[0].formula1
    ranges = {str(cf.sqref): cf.rules for cf in plan.conditional_formatting}
    assert f"{sev}{FIRST_ROW}:{sev}1000" in ranges and f"{status}{FIRST_ROW}:{status}1000" in ranges
    sev_fills = {r.formula[0].strip('"'): r.dxf.fill.bgColor.rgb[-6:] for r in ranges[f"{sev}{FIRST_ROW}:{sev}1000"]}
    assert sev_fills["High"] == "F9D9B8" and sev_fills["Medium"] == "FBEEB5" and sev_fills["Low"] == "D6E9F8" and sev_fills["Info"] == "E4E7EB"
    st_fills = {r.formula[0].strip('"'): r.dxf.fill.bgColor.rgb[-6:] for r in ranges[f"{status}{FIRST_ROW}:{status}1000"]}
    assert st_fills["Pass"] == "D5ECD9" and st_fills["Fail"] == "F4C7C3" and st_fills["Not Started"] == "F1F3F5" and st_fills["N/A"] == "E4E7EB"


def test_filtered_export(analysis):
    ids = [analysis.test_cases[2].id, analysis.test_cases[5].id, "TC-NOPE"]
    wb = load(build_workbook(analysis, ids))
    plan = wb["Endpoint Test Plan"]
    assert [plan.cell(r, 2).value for r in range(FIRST_ROW, plan.max_row + 1)] == ids[:2]
    assert "Filtered export (2 of" in all_text(wb["Summary"])
    empty = load(build_workbook(analysis, []))
    assert empty["Endpoint Test Plan"].max_row == HEADER_ROW  # header only
    got = {label: evaluate(empty, f) for label, f in summary_formula_cells(empty["Summary"])}
    assert got["Test cases in this report"] == 0 and got["Endpoints covered by this report"] == 0 and got["High"] == 0


# ------------------------------------------------------------------------------------------------ summary / cover
def summary_formula_cells(ws):
    return [(row[1].value, row[2].value) for row in ws.iter_rows(min_row=6) if isinstance(row[2].value, str) and row[2].value.startswith("=")]


def test_summary_formulas_calculate_to_the_data(workbook, analysis):
    ws = workbook["Summary"]
    cells = {label: f for label, f in summary_formula_cells(ws)}
    got = {label: evaluate(workbook, f) for label, f in cells.items()}
    sev, st = Counter(t.severity for t in analysis.test_cases), Counter(t.status for t in analysis.test_cases)
    for s in ("High", "Medium", "Low", "Info"):
        assert got[s] == sev.get(s, 0), s
    for s in ("Not Started", "Pass", "Fail", "N/A"):
        assert got[s] == st.get(s, 0), s
    owasp = Counter(t.owasp_api.split(" ")[0] for t in analysis.test_cases)
    for label, n in got.items():
        m = re.match(r"(API\d+:2023)  ", label)
        if m:
            assert n == owasp.get(m.group(1), 0), label
    cat = Counter(t.category for t in analysis.test_cases)
    for c, n in cat.items():
        assert got[c] == n, c
    assert got["Endpoints in the collection"] == len(analysis.endpoints)
    assert got["Endpoints covered by this report"] == len({t.endpoint_id for t in analysis.test_cases})
    assert got["Test cases in this report"] == len(analysis.test_cases)
    assert got["Static findings"] == len(analysis.findings)
    assert got["Environment findings"] == 0
    assert sum(n for lbl, n in got.items() if lbl.startswith("API")) == len(analysis.test_cases)


def test_summary_counts_follow_status_changes_and_filtered_exports(analysis):
    analysis.test_cases[0].status = "Pass"
    analysis.test_cases[1].status = "Fail"
    ids = [t.id for t in analysis.test_cases[:10]]
    wb = load(build_workbook(analysis, ids))
    got = {label: evaluate(wb, f) for label, f in summary_formula_cells(wb["Summary"])}
    assert got["Pass"] == 1 and got["Fail"] == 1 and got["Test cases in this report"] == 10
    assert got["Not Started"] == 8


def test_formulas_reference_only_the_shifted_ranges(workbook, analysis):
    n = len(analysis.test_cases) + HEADER_ROW
    formulas = [f for _l, f in summary_formula_cells(workbook["Summary"])]
    assert any(f"$L${FIRST_ROW}:$L${n}" in f for f in formulas)  # severity column
    assert any(f"$M${FIRST_ROW}:$M${n}" in f for f in formulas)  # status column
    assert not any("$A$" in f or "!$A" in f for f in formulas)


def test_cover_sheet_content(workbook, analysis):
    ws = workbook["Summary"]
    assert ws["B2"].value == "API Security Assessment: Test Plan" and ws["B2"].font.size >= 22
    assert {"B2:H2", "B3:H3", "B4:H4"} <= {str(m) for m in ws.merged_cells.ranges}
    assert ws["B3"].value == analysis.collection.name
    assert ws["B4"].fill.fgColor.rgb.endswith("0C7C8C")  # thin teal line
    labels = {ws.cell(r, 2).value: ws.cell(r, 3).value for r in range(6, 25)}
    for label in ("Client", "Application / API name", "Collection file", "Report date", "Version", "Prepared by", "Reviewed by", "Classification"):
        assert label in labels, label
    assert labels["Version"] == 1.0 and labels["Application / API name"] == analysis.collection.name
    assert labels["Client"].startswith("Enter")  # editable placeholder
    label_cell = next(c for row in ws.iter_rows(min_row=6, max_row=25) for c in row if c.value == "Client")
    assert label_cell.fill.fgColor.rgb.endswith("EEF2F6") and label_cell.font.bold
    text = all_text(ws)
    assert "Scope and Methodology" in text and "No requests were sent" in text and "authorized tester" in text
    for std in ("OWASP API Security Top 10", "OWASP ASVS 4.0", "CWE", "OWASP WSTG"):
        assert std in text
    assert "Results at a Glance" in text


def test_cover_shows_uploaded_file_name(postman_bytes):
    coll = parse_bytes(postman_bytes)
    a = analyze_collection(coll)
    a.collection.file_name = "demo-shop.postman_collection.json"
    ws = load(build_workbook(a))["Summary"]
    assert "demo-shop.postman_collection.json" in all_text(ws)


def test_summary_charts_use_muted_palette(workbook):
    charts = workbook["Summary"]._charts
    assert len(charts) == 2
    for ch in charts:
        fills = [pt.graphicalProperties.solidFill.srgbClr for pt in ch.series[0].dPt]
        colors = {getattr(f, 'val', f) for f in fills}
        assert colors and all(len(c) == 6 for c in colors)
        assert not (colors & {"FF0000", "00FF00", "0000FF", "FFFF00"})  # no bright primaries


def test_disclaimer_and_credit_are_the_last_rows_with_a_real_hyperlink(workbook):
    ws = workbook["Summary"]
    rows = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 2).value]
    last, prev = ws.cell(rows[-1], 2), ws.cell(rows[-2], 2)
    assert prev.value == SAFETY_NOTE
    assert last.value == f"Built by Hard Pansara | {CREDIT_URL}"
    assert last.hyperlink and last.hyperlink.target == CREDIT_URL
    assert last.font.color.rgb.endswith("0C7C8C") and last.font.underline == "single"


# ------------------------------------------------------------------------------------------------ print + properties
def test_print_setup_and_properties(workbook, analysis):
    for ws in workbook:
        assert ws.page_setup.orientation == ("portrait" if ws.title == "Summary" else "landscape")
        assert ws.page_setup.fitToWidth == 1 and ws.page_setup.fitToHeight == 0
        assert ws.sheet_properties.pageSetUpPr.fitToPage is True
        assert ws.print_area.startswith("'" + ws.title + "'!$B$2:") or "$B$2:" in ws.print_area
        assert ws.page_margins.left <= 0.5
        assert ws.oddHeader.left.text == "API Security Assessment: Test Plan" and ws.oddHeader.right.text == "Confidential"
        assert ws.oddFooter.center.text == "Page &P of &N" and ws.oddFooter.left.text.startswith("Generated ")
        if ws.title != "Summary":
            assert ws.print_title_rows.replace("$", "") == "5:5"
    assert analysis.collection.name in workbook.properties.title
    assert workbook.properties.subject and workbook.properties.creator


# ------------------------------------------------------------------------------------------------ safety
def test_user_text_is_never_a_formula(analysis):
    analysis.test_cases[0].notes = '=HYPERLINK("http://evil.example","x")'
    analysis.endpoints[0].url = "=1+1"
    plan = load(build_workbook(analysis))["Endpoint Test Plan"]
    notes_cell = plan.cell(FIRST_ROW, col_of(plan, "Notes"))
    assert notes_cell.data_type == "s" and notes_cell.value.startswith("=HYPERLINK")


def test_no_raw_secret_values_anywhere_in_the_workbook(postman, env_bytes):
    env = build_environment(load_document(env_bytes))
    wb = load(build_workbook(analyze_collection(postman, env)))
    dump = " ".join(all_text(ws) for ws in wb)
    assert "Pass****" in dump or "eyJh****" in dump
    for secret in RAW_SECRETS:
        assert secret not in dump, secret


def test_env_sheet_content_and_summary_row(postman, env_bytes):
    env = build_environment(load_document(env_bytes))
    a = analyze_collection(postman, env)
    wb = load(build_workbook(a))
    ws = wb["Environment Findings"]
    n_env = sum(1 for f in a.findings if f.group == "Environment")
    assert n_env > 0 and ws.max_row == n_env + HEADER_ROW and ws["B5"].value == "Finding ID"
    got = {label: evaluate(wb, f) for label, f in summary_formula_cells(wb["Summary"])}
    assert got["Environment findings"] == n_env and got["Static findings"] == len(a.findings) - n_env
    assert "Demo Shop - Staging (applied)" in all_text(wb["Summary"])


def test_openapi_export_and_filename(openapi):
    a = analyze_collection(openapi)
    assert len(build_workbook(a)) > 5000
    assert export_filename(a, False).startswith("api-security-test-plan-library-api-sample")
    assert export_filename(a, True).endswith(".xlsx") and "-filtered-" in export_filename(a, True)
    json.dumps(a.model_dump())  # still serializable
