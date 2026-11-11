"""Endpoint trait detection used to choose which security tests apply."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import Endpoint
from ..parsers.common import path_of
from ..rules.base import STATE_CHANGING, WRITE_METHODS
from ..rules.rules import id_path_params, literal_id_segments

_URL_SUBSTR = ("url", "uri", "link", "callback", "webhook", "redirect", "domain", "proxy", "feed", "host",
               "dest", "returnto", "return_to", "endpoint")
_URL_EXACT = {"next", "continue", "return", "target", "src", "image", "goto", "forward", "site", "website"}
_REDIRECT_SUBSTR = ("redirect", "returnto", "return_to", "callback", "goto", "forward", "dest")
_REDIRECT_EXACT = {"next", "continue", "return", "url"}
_PAGINATION = {"page", "limit", "offset", "per_page", "perpage", "size", "page_size", "pagesize", "cursor", "skip", "take", "count"}
_AUTH_FLOW_RE = re.compile(r"(login|signin|sign-in|authenticate|oauth|token|password|passwd|reset|forgot|otp|2fa|mfa|verify|register|signup|sign-up)", re.I)
_LOGIN_RE = re.compile(r"(login|signin|sign-in|authenticate|oauth/token|/token)", re.I)
_RESET_RE = re.compile(r"(password|passwd|reset|forgot|recover)", re.I)
_OTP_RE = re.compile(r"(otp|2fa|mfa|verify|verification|code)", re.I)
_ENUM_RE = re.compile(r"(login|signin|sign-in|forgot|reset|register|signup|sign-up|recover|authenticate)", re.I)
_UPLOAD_PATH_RE = re.compile(r"(upload|avatar|attachment|import|file|image|photo|document)", re.I)
_ADMIN_RE = re.compile(r"/(admin|administrator|debug|actuator|internal|management|console)(/|$)", re.I)


def _leaf(name: str) -> str:
    return name.split(".")[-1].replace("[]", "")


@dataclass
class Traits:
    id_params: list[str] = field(default_factory=list)
    has_auth: bool = False
    has_body: bool = False
    json_body: bool = False
    inputs: list[str] = field(default_factory=list)  # injectable inputs (top-level body fields + query params)
    url_params: list[str] = field(default_factory=list)
    redirect_params: list[str] = field(default_factory=list)
    is_list: bool = False
    is_auth_flow: bool = False
    is_login: bool = False
    is_reset: bool = False
    is_otp: bool = False
    enumerates_users: bool = False
    is_upload: bool = False
    state_changing: bool = False
    is_admin_path: bool = False
    plain_http: bool = False
    token_based: bool = False  # bearer / oauth2 / other token auth (JWT-style tests apply)


def detect_traits(ep: Endpoint) -> Traits:
    path = path_of(ep.url)
    t = Traits()
    t.id_params = id_path_params(ep) + literal_id_segments(ep)
    t.id_params += [q for q in ep.query_params if re.search(r"(^id$|_id$|Id$)", q)]
    t.has_auth = ep.auth_type != "none"
    t.token_based = ep.auth_type in {"bearer", "oauth2", "other"}
    ct = (ep.body_content_type or "").lower()
    t.has_body = ep.method in {"POST", "PUT", "PATCH"} and bool(ep.body_fields or ct)
    t.json_body = "json" in ct or (t.has_body and not ct and bool(ep.body_fields))
    top_body = [f for f in ep.body_fields if "." not in f and "[" not in f]
    t.inputs = list(dict.fromkeys(top_body + ep.query_params))
    names = ep.body_fields + ep.query_params
    for n in names:
        lf = _leaf(n).lower()
        if any(s in lf for s in _URL_SUBSTR) or lf in _URL_EXACT:
            t.url_params.append(n)
        if any(s in lf for s in _REDIRECT_SUBSTR) or lf in _REDIRECT_EXACT:
            t.redirect_params.append(n)
    segs = [s for s in path.split("/") if s]
    last = segs[-1] if segs else ""
    last_is_param = last.startswith(":") or last.startswith("{") or bool(literal_id_segments(ep) and last in literal_id_segments(ep))
    paginated = any(q.lower() in _PAGINATION for q in ep.query_params)
    t.is_list = ep.method == "GET" and not last_is_param and (
        paginated or last.lower().endswith("s") or last.lower() in {"list", "search", "all"})
    t.is_auth_flow = bool(_AUTH_FLOW_RE.search(path)) and ep.method in {"POST", "PUT", "PATCH", "GET"}
    t.is_login = bool(_LOGIN_RE.search(path))
    t.is_reset = bool(_RESET_RE.search(path))
    t.is_otp = bool(_OTP_RE.search(path))
    t.enumerates_users = bool(_ENUM_RE.search(path))
    t.is_upload = ep.has_file_upload or "multipart" in ct or (ep.method in {"POST", "PUT"} and bool(_UPLOAD_PATH_RE.search(segs[-1] if segs else "")))
    t.state_changing = ep.method in STATE_CHANGING or ep.method in WRITE_METHODS
    t.is_admin_path = bool(_ADMIN_RE.search(path + "/"))
    t.plain_http = ep.url.lower().startswith("http://")
    return t
