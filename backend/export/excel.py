"""In-memory Excel report, styled as a client-ready security assessment deliverable.

The workbook is built with openpyxl and saved to io.BytesIO (nothing touches the disk).

Layout rules shared by every sheet: row 1 and column A are an empty margin, content starts at B2, gridlines are
hidden, zoom is 90%. Table sheets have a title (B2), a muted subtitle (B3), a blank row 4 and the table header on
row 5 (data from row 6). Formulas, the Status dropdown and conditional formats all reference these shifted ranges.
"""
from __future__ import annotations

import io
import math
import re
from datetime import date

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from ..models import (
    CREDIT_NAME, CREDIT_URL, SAFETY_NOTE, SEVERITIES, STATUSES, AnalysisResult, Endpoint, Finding, TestCase,
)
from ..standards import ASVS, CWE, OWASP_API, STANDARDS_SUMMARY, WSTG

SHEET_SUMMARY = "Summary"
SHEET_PLAN = "Endpoint Test Plan"
SHEET_FINDINGS = "Static Findings"
SHEET_ENV = "Environment Findings"
SHEET_STANDARDS = "Standards Reference"

REPORT_TITLE = "API Security Assessment: Test Plan"
CLASSIFICATION = "Confidential"
REPORT_VERSION = "1.0"

# ---------------------------------------------------------------------------------------------- palette
NAVY, SLATE, TEAL, PANEL, GRID = "1B2A41", "324A5F", "0C7C8C", "EEF2F6", "C9D1D9"
TEXT, MUTED, BAND, WHITE = "1F2933", "5F6B7A", "F7F9FB", "FFFFFF"
GROUP_LINE = "8FA0B3"

SEV_COLORS = {  # fill, text
    "Critical": ("F4C7C3", "7A1F18"), "High": ("F9D9B8", "8A4B08"), "Medium": ("FBEEB5", "6B5600"),
    "Low": ("D6E9F8", "1F4E79"), "Info": ("E4E7EB", "3E4C59"),
}
STATUS_COLORS = {
    "Pass": ("D5ECD9", "1E5B2E"), "Fail": ("F4C7C3", "7A1F18"),
    "Not Started": ("F1F3F5", "5F6B7A"), "N/A": ("E4E7EB", "3E4C59"),
}
# Muted bar colours for the charts (never a rainbow)
CHART_SEV = {"High": "C98A4B", "Medium": "C9AE45", "Low": "6E9CC4", "Info": "9AA5B1"}
CHART_STATUS = {"Not Started": "A9B2BC", "Pass": "6FA37C", "Fail": "C77A72", "N/A": "C3C9D0"}

FONT = "Calibri"
MONO = "Consolas"

FIRST_COL = 2          # column B
HEADER_ROW = 5
FIRST_ROW = 6


# ---------------------------------------------------------------------------------------------- styles
def font(size=10, bold=False, color=TEXT, name=FONT, italic=False, underline=None) -> Font:
    return Font(name=name, size=size, bold=bold, color=color, italic=italic, underline=underline)


def fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color, bgColor=color)


def side(style: str = "thin", color: str = GRID) -> Side:
    return Side(style=style, color=color)


LEFT_TOP_WRAP = Alignment(wrap_text=True, vertical="top", horizontal="left")
LEFT_CENTER = Alignment(wrap_text=True, vertical="center", horizontal="left")


def _put(ws: Worksheet, row: int, col: int, value, *, f: Font | None = None, fl: PatternFill | None = None,
         al: Alignment | None = None, border: Border | None = None):
    c = ws.cell(row=row, column=col, value=value)
    if isinstance(value, str) and value.startswith("="):
        c.data_type = "s"  # user text is never evaluated as a formula; real formulas go through _formula()
    c.font = f or font()
    if fl:
        c.fill = fl
    c.alignment = al or LEFT_TOP_WRAP
    if border:
        c.border = border
    return c


def _formula(ws: Worksheet, row: int, col: int, formula: str, **kw):
    c = _put(ws, row, col, None, **kw)
    c.value = formula
    c.data_type = "f"
    return c


def _setup_sheet(ws: Worksheet, tab_color: str, widths: dict[int, float]):
    """Margin (row 1 / column A), hidden gridlines, 90% zoom, tab colour, column widths."""
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 90
    ws.sheet_properties.tabColor = tab_color
    ws.column_dimensions["A"].width = 2
    ws.row_dimensions[1].height = 10
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w


def _print_setup(ws: Worksheet, area: str, title_rows: str | None, generated: str, landscape: bool = True):
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.paperSize = 9  # A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.print_area = area
    if title_rows:
        ws.print_title_rows = title_rows
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.7, bottom=0.65, header=0.3, footer=0.3)
    ws.oddHeader.left.text = REPORT_TITLE
    ws.oddHeader.left.size = 9
    ws.oddHeader.right.text = CLASSIFICATION
    ws.oddHeader.right.size = 9
    ws.oddFooter.left.text = f"Generated {generated}"
    ws.oddFooter.left.size = 9
    ws.oddFooter.center.text = "Page &P of &N"
    ws.oddFooter.center.size = 9


def _sheet_title(ws: Worksheet, title: str, subtitle: str):
    _put(ws, 2, FIRST_COL, title, f=font(18, True, NAVY), al=Alignment(vertical="center"))
    ws.row_dimensions[2].height = 28
    _put(ws, 3, FIRST_COL, subtitle, f=font(10, False, MUTED, italic=True), al=Alignment(vertical="center"))
    ws.row_dimensions[3].height = 16
    ws.row_dimensions[4].height = 8


def _header_row(ws: Worksheet, headers: list[str], widths: list[float], row: int = HEADER_ROW):
    white = side("thin", WHITE)
    for i, (h, w) in enumerate(zip(headers, widths)):
        col = FIRST_COL + i
        _put(ws, row, col, h, f=font(10, True, WHITE), fl=fill(NAVY),
             al=Alignment(wrap_text=True, vertical="center", horizontal="left"), border=Border(left=white, right=white))
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[row].height = 30


def _est_lines(text, width: float, mono: bool = False) -> int:
    if text is None or text == "":
        return 1
    per_line = max(1, int(width * (0.70 if mono else 0.98)))
    return sum(max(1, math.ceil(len(seg) / per_line)) for seg in str(text).split("\n"))


def _body_row(ws: Worksheet, row: int, values: list, widths: list[float], mono_cols: set[int], *, banded: bool,
              group_start: bool = False):
    """One table row: light banding, thin grey bottom border, optional thicker top border, auto-fitted height."""
    lines = 1
    for i, v in enumerate(values):
        mono = i in mono_cols
        c = _put(ws, row, FIRST_COL + i, v, f=font(10, False, TEXT, MONO if mono else FONT), fl=fill(BAND) if banded else None)
        c.border = Border(bottom=side("thin", GRID), top=side("medium", GROUP_LINE) if group_start else None)
        lines = max(lines, _est_lines(v, widths[i], mono))
    ws.row_dimensions[row].height = min(409, max(16, 13.2 * lines + 7))


def _color_rules(ws: Worksheet, rng: str, colors: dict[str, tuple[str, str]]):
    for value, (bg, fg) in colors.items():
        ws.conditional_formatting.add(rng, CellIsRule(
            operator="equal", formula=[f'"{value}"'], fill=PatternFill("solid", bgColor=bg, fgColor=bg),
            font=Font(color=fg, bold=True)))


# ---------------------------------------------------------------------------------------------- data helpers
def standard_tags(tc: TestCase) -> str:
    """Short tags: 'API1:2023 | CWE-639 | ASVS V4.2.1 | WSTG-ATHZ-04'."""
    parts = [tc.owasp_api.split(" ")[0], *tc.cwe, *[f"ASVS {a}" for a in tc.asvs], *tc.wstg]
    return " | ".join(parts)


standard_reference = standard_tags  # backwards-compatible name


def finding_tags(f: Finding) -> str:
    return " | ".join(f.standard_refs)


def numbered_steps(steps: list[str]) -> str:
    return "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))


def _endpoint_label(ep: Endpoint | None, eid: str | None) -> str:
    return "Collection-wide" if not eid or ep is None else f"{ep.id} {ep.method} {ep.url}"


def select_test_cases(analysis: AnalysisResult, ids: list[str] | None) -> list[TestCase]:
    if ids is None:
        return list(analysis.test_cases)
    wanted = set(ids)
    return [t for t in analysis.test_cases if t.id in wanted]


# ---------------------------------------------------------------------------------------------- Endpoint Test Plan
PLAN_HEADERS = ["Test ID", "Endpoint ID", "Method", "URL", "Auth", "Test to perform", "Category", "How to test",
                "Expected secure result", "Standard reference (OWASP API / CWE / ASVS / WSTG)", "Severity", "Status", "Notes"]
PLAN_WIDTHS = [12, 12, 10, 40, 14, 34, 20, 60, 40, 30, 12, 14, 30]
PLAN_MONO = {0, 1, 2, 3}  # IDs, method and URL use the monospace font
PLAN_COL = {h: FIRST_COL + i for i, h in enumerate(PLAN_HEADERS)}


def _pl(header: str) -> str:
    return get_column_letter(PLAN_COL[header])


COL_TESTID, COL_ENDPOINT = _pl("Test ID"), _pl("Endpoint ID")
COL_CATEGORY = _pl("Category")
COL_STANDARD = _pl("Standard reference (OWASP API / CWE / ASVS / WSTG)")
COL_SEVERITY, COL_STATUS, COL_NOTES = _pl("Severity"), _pl("Status"), _pl("Notes")


def _plan_sheet(wb: Workbook, analysis: AnalysisResult, cases: list[TestCase], generated: str) -> int:
    ws = wb.create_sheet(SHEET_PLAN)
    _setup_sheet(ws, TEAL, {})
    _sheet_title(ws, "Endpoint Test Plan", "Security test cases per endpoint. Record the result in Status and add evidence in Notes.")
    _header_row(ws, PLAN_HEADERS, PLAN_WIDTHS)
    eps = {e.id: e for e in analysis.endpoints}
    prev_ep, band = None, False
    for i, tc in enumerate(cases):
        ep = eps.get(tc.endpoint_id)
        group_start = tc.endpoint_id != prev_ep
        if group_start and prev_ep is not None:
            band = not band  # banding alternates per endpoint group so groups stay readable
        prev_ep = tc.endpoint_id
        vals = [tc.id, tc.endpoint_id, ep.method if ep else "", ep.url if ep else "", ep.auth_type if ep else "",
                tc.title, tc.category, numbered_steps(tc.how_to_test), tc.expected_result, standard_tags(tc),
                tc.severity, tc.status, tc.notes]
        _body_row(ws, FIRST_ROW + i, vals, PLAN_WIDTHS, PLAN_MONO, banded=band, group_start=group_start and i > 0)
    last = max(len(cases) + HEADER_ROW, FIRST_ROW)
    ws.freeze_panes = f"{get_column_letter(FIRST_COL + 1)}{FIRST_ROW}"  # below the header, right of Test ID
    last_col = get_column_letter(FIRST_COL + len(PLAN_HEADERS) - 1)
    ws.auto_filter.ref = f"B{HEADER_ROW}:{last_col}{last}"
    cf_last = max(last, 1000)  # formatting/validation also cover rows a tester might add
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=False,
                        showErrorMessage=True, errorTitle="Invalid status", error="Choose Not Started, Pass, Fail or N/A.")
    ws.add_data_validation(dv)
    dv.add(f"{COL_STATUS}{FIRST_ROW}:{COL_STATUS}{cf_last}")
    _color_rules(ws, f"{COL_SEVERITY}{FIRST_ROW}:{COL_SEVERITY}{cf_last}", SEV_COLORS)
    _color_rules(ws, f"{COL_STATUS}{FIRST_ROW}:{COL_STATUS}{cf_last}", STATUS_COLORS)
    _print_setup(ws, f"B2:{last_col}{last}", f"{HEADER_ROW}:{HEADER_ROW}", generated)
    return last


# ---------------------------------------------------------------------------------------------- findings sheets
FINDING_HEADERS = ["Finding ID", "Endpoint", "Issue", "Evidence (masked)", "Severity", "Standard reference", "Remediation"]
FINDING_WIDTHS = [12, 44, 40, 44, 12, 30, 56]
ENV_HEADERS = ["Finding ID", "Issue", "Evidence (masked)", "Severity", "Standard reference", "Remediation"]
ENV_WIDTHS = [12, 52, 52, 12, 30, 60]


def _findings_table(ws: Worksheet, headers, widths, mono, rows: list[list], sev_index: int, generated: str):
    _header_row(ws, headers, widths)
    for i, vals in enumerate(rows):
        _body_row(ws, FIRST_ROW + i, vals, widths, mono, banded=i % 2 == 1)
    last = max(len(rows) + HEADER_ROW, FIRST_ROW)
    last_col = get_column_letter(FIRST_COL + len(headers) - 1)
    ws.freeze_panes = f"{get_column_letter(FIRST_COL + 1)}{FIRST_ROW}"
    ws.auto_filter.ref = f"B{HEADER_ROW}:{last_col}{last}"
    sev = get_column_letter(FIRST_COL + sev_index)
    _color_rules(ws, f"{sev}{FIRST_ROW}:{sev}{max(last, 500)}", SEV_COLORS)
    _print_setup(ws, f"B2:{last_col}{last}", f"{HEADER_ROW}:{HEADER_ROW}", generated)
    return last


def _findings_sheet(wb: Workbook, analysis: AnalysisResult, generated: str) -> int:
    ws = wb.create_sheet(SHEET_FINDINGS)
    _setup_sheet(ws, SLATE, {})
    _sheet_title(ws, "Static Findings", "Misconfigurations detected by analysing the collection itself. No requests were sent.")
    eps = {e.id: e for e in analysis.endpoints}
    rows = [[f.id, _endpoint_label(eps.get(f.endpoint_id), f.endpoint_id), f.issue, f.evidence_masked, f.severity,
             finding_tags(f), f.remediation] for f in analysis.findings if f.group != "Environment"]
    return _findings_table(ws, FINDING_HEADERS, FINDING_WIDTHS, {0, 1, 3}, rows, 4, generated)


def _env_sheet(wb: Workbook, analysis: AnalysisResult, generated: str) -> int:
    ws = wb.create_sheet(SHEET_ENV)
    _setup_sheet(ws, "5B7C99", {})
    _sheet_title(ws, "Environment Findings", "Issues found in the Postman environment file. Secret values are masked.")
    rows = [[f.id, f.issue, f.evidence_masked, f.severity, finding_tags(f), f.remediation]
            for f in analysis.findings if f.group == "Environment"]
    return _findings_table(ws, ENV_HEADERS, ENV_WIDTHS, {0, 2}, rows, 3, generated)


# ---------------------------------------------------------------------------------------------- Standards Reference
def _standards_sheet(wb: Workbook, generated: str):
    ws = wb.create_sheet(SHEET_STANDARDS)
    _setup_sheet(ws, "5F6B7A", {})
    _sheet_title(ws, "Standards Reference", "The security standards used to classify every test case and finding.")
    headers, widths = ["Standard", "Reference", "Title", "Description"], [34, 16, 52, 80]
    _header_row(ws, headers, widths)
    rows: list[tuple[list[str], bool]] = []
    for name, line in STANDARDS_SUMMARY:
        rows.append(([name, "Overview", "", line], True))
    for key, (title, desc) in OWASP_API.items():
        rows.append((["OWASP API Security Top 10 2023", f"{key}:2023", title, desc], False))
    for rid, desc in ASVS.items():
        rows.append((["OWASP ASVS 4.0", rid, desc.split(".")[0], desc], False))
    for rid, title in CWE.items():
        rows.append((["CWE", rid, title, f"https://cwe.mitre.org/data/definitions/{rid.split('-')[1]}.html"], False))
    for rid, title in WSTG.items():
        rows.append((["OWASP WSTG", rid, title, "OWASP Web Security Testing Guide test procedure."], False))
    for i, (vals, overview) in enumerate(rows):
        r = FIRST_ROW + i
        _body_row(ws, r, vals, widths, {1}, banded=i % 2 == 1)
        if overview:
            for c in range(FIRST_COL, FIRST_COL + 4):
                cell = ws.cell(row=r, column=c)
                cell.fill = fill(PANEL)
                cell.font = font(10, True, NAVY, MONO if c == FIRST_COL + 1 else FONT)
    last = FIRST_ROW + len(rows) - 1
    ws.freeze_panes = f"{get_column_letter(FIRST_COL + 1)}{FIRST_ROW}"
    ws.auto_filter.ref = f"B{HEADER_ROW}:E{last}"
    _print_setup(ws, f"B2:E{last}", f"{HEADER_ROW}:{HEADER_ROW}", generated)


# ---------------------------------------------------------------------------------------------- Summary (cover)
SUMMARY_WIDTHS = {2: 52, 3: 16, 4: 3, 5: 15, 6: 15, 7: 15, 8: 15}
LAST_SUM_COL = 8  # column H


def _bar(ws: Worksheet, row: int, text: str):
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=LAST_SUM_COL)
    for c in range(2, LAST_SUM_COL + 1):
        ws.cell(row=row, column=c).fill = fill(SLATE)
    _put(ws, row, 2, text, f=font(11, True, WHITE), fl=fill(SLATE), al=Alignment(vertical="center", indent=1))
    ws.row_dimensions[row].height = 20


def _mini_header(ws: Worksheet, row: int, left: str, right: str):
    white = side("thin", WHITE)
    _put(ws, row, 2, left, f=font(10, True, WHITE), fl=fill(NAVY), al=Alignment(vertical="center", indent=1), border=Border(right=white))
    _put(ws, row, 3, right, f=font(10, True, WHITE), fl=fill(NAVY), al=Alignment(vertical="center", horizontal="center"))
    ws.row_dimensions[row].height = 20


def _count_row(ws: Worksheet, row: int, label: str, formula: str, *, label_fill: str | None = None,
               label_font: Font | None = None, banded: bool = False):
    bottom = Border(bottom=side("thin", GRID))
    _put(ws, row, 2, label, f=label_font or font(10), fl=fill(label_fill) if label_fill else (fill(BAND) if banded else None),
         al=Alignment(vertical="center", indent=1), border=bottom)
    _formula(ws, row, 3, formula, f=font(10, True, NAVY), fl=fill(BAND) if banded else None,
             al=Alignment(vertical="center", horizontal="center"), border=bottom)
    ws.row_dimensions[row].height = 18


def _bar_chart(ws: Worksheet, title: str, anchor: str, first_row: int, last_row: int, colors: list[str]):
    ch = BarChart()
    ch.type = "col"
    ch.title = title
    ch.title.overlay = False  # keep the title above the plot area
    ch.legend = None
    ch.height, ch.width = 5.6, 12.2
    ch.gapWidth = 60
    ch.add_data(Reference(ws, min_col=3, min_row=first_row, max_row=last_row), titles_from_data=False)
    ch.set_categories(Reference(ws, min_col=2, min_row=first_row, max_row=last_row))
    s = ch.series[0]
    s.graphicalProperties.solidFill = SLATE
    s.graphicalProperties.line.solidFill = SLATE
    for i, col in enumerate(colors):
        pt = DataPoint(idx=i)
        pt.graphicalProperties.solidFill = col
        pt.graphicalProperties.line.solidFill = col
        s.dPt.append(pt)
    ch.dataLabels = DataLabelList()
    ch.dataLabels.showVal = True
    ch.dataLabels.showSerName = False
    ch.dataLabels.showCatName = False
    ch.dataLabels.showLegendKey = False
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.y_axis.numFmt = "0"
    ch.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="E3E7EC", w=6350))  # light grid
    ws.add_chart(ch, anchor)


def _summary_sheet(wb: Workbook, analysis: AnalysisResult, cases: list[TestCase], plan_last: int, filtered: bool, generated: str):
    ws = wb.active
    ws.title = SHEET_SUMMARY
    _setup_sheet(ws, NAVY, SUMMARY_WIDTHS)
    plan = f"'{SHEET_PLAN}'"
    last_plan = max(plan_last, FIRST_ROW)

    def rng(col: str) -> str:
        return f"{plan}!${col}${FIRST_ROW}:${col}${last_plan}"

    # ---- title block
    ws.merge_cells("B2:H2")
    _put(ws, 2, 2, REPORT_TITLE, f=font(24, True, NAVY), al=Alignment(vertical="center"))
    ws.row_dimensions[2].height = 40
    ws.merge_cells("B3:H3")
    _put(ws, 3, 2, analysis.collection.name, f=font(13, False, MUTED), al=Alignment(vertical="center"))
    ws.row_dimensions[3].height = 22
    ws.merge_cells("B4:H4")
    for c in range(2, LAST_SUM_COL + 1):
        ws.cell(row=4, column=c).fill = fill(TEAL)
    ws.row_dimensions[4].height = 3

    # ---- document information
    r = 6
    _bar(ws, r, "Document Information")
    r += 1
    env = analysis.environment
    info: list[tuple[str, str | float, bool]] = [  # label, value, is_hint (an editable placeholder)
        ("Client", "Enter client name", True),
        ("Application / API name", analysis.collection.name, False),
        ("Collection file", analysis.collection.file_name or "Not recorded", not analysis.collection.file_name),
        ("Source type", analysis.collection.source_type, False),
        ("Environment file", (env.name + (" (applied)" if env.applied else " (reviewed only)")) if env else "none", False),
        ("Report date", generated, False),
        ("Version", float(REPORT_VERSION), False),  # a real number (formatted 0.0) so Excel shows no text-number warning
        ("Scope of this report", f"Filtered export ({len(cases)} of {len(analysis.test_cases)} test cases)" if filtered
         else "All test cases", False),
        ("Prepared by", "Enter name", True),
        ("Reviewed by", "Enter name", True),
        ("Classification", CLASSIFICATION, False),
    ]
    for label, value, hint in info:
        bottom = Border(bottom=side("thin", GRID))
        _put(ws, r, 2, label, f=font(10, True, NAVY), fl=fill(PANEL), al=Alignment(vertical="center", indent=1), border=bottom)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=LAST_SUM_COL)
        for c in range(3, LAST_SUM_COL + 1):
            ws.cell(row=r, column=c).border = bottom
        vc = _put(ws, r, 3, value, f=font(10, False, MUTED if hint else TEXT, italic=hint), al=Alignment(vertical="center", horizontal="left", indent=1), border=bottom)
        if isinstance(value, float):
            vc.number_format = "0.0"
        ws.row_dimensions[r].height = 18
        r += 1

    # ---- scope and methodology
    r += 1
    _bar(ws, r, "Scope and Methodology")
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=LAST_SUM_COL)
    _put(ws, r, 2,
         "This test plan is the result of static analysis of the uploaded API collection. The collection was parsed to identify every "
         "endpoint, security test cases were selected from each endpoint's characteristics, and the collection was checked for common "
         "misconfigurations. No requests were sent to any target. The test cases are to be executed by an authorized tester, who records "
         "the outcome in the Status and Notes columns of the Endpoint Test Plan sheet.",
         f=font(10), al=Alignment(wrap_text=True, vertical="top", indent=1))
    ws.row_dimensions[r].height = 64
    r += 2

    # ---- standards
    _bar(ws, r, "Security Standards Referenced")
    r += 1
    for name, line in STANDARDS_SUMMARY:
        bottom = Border(bottom=side("thin", GRID))
        _put(ws, r, 2, name, f=font(10, True, NAVY), fl=fill(PANEL), al=Alignment(vertical="center", wrap_text=True, indent=1), border=bottom)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=LAST_SUM_COL)
        _put(ws, r, 3, line, f=font(10), al=Alignment(vertical="center", wrap_text=True, indent=1), border=bottom)
        ws.row_dimensions[r].height = 30
        r += 1
    r += 1

    # ---- results at a glance: every number is a formula over the Endpoint Test Plan sheet
    _bar(ws, r, "Results at a Glance")
    r += 2
    n_static = sum(1 for f in analysis.findings if f.group != "Environment")
    n_env = len(analysis.findings) - n_static
    _mini_header(ws, r, "Overview", "Count")
    r += 1
    ep_formula = f"=ROUND(SUMPRODUCT(1/COUNTIF({rng(COL_ENDPOINT)},{rng(COL_ENDPOINT)})),0)" if cases else "=0"
    kpis = [
        ("Endpoints in the collection", f"={len(analysis.endpoints)}"),
        ("Endpoints covered by this report", ep_formula),
        ("Test cases in this report", f"=COUNTA({rng(COL_TESTID)})" if cases else "=0"),
        ("Static findings", f"=COUNTA('{SHEET_FINDINGS}'!$B${FIRST_ROW}:$B${n_static + HEADER_ROW})" if n_static else "=0"),
        ("Environment findings", f"=COUNTA('{SHEET_ENV}'!$B${FIRST_ROW}:$B${n_env + HEADER_ROW})" if n_env else "=0"),
    ]
    for i, (label, fml) in enumerate(kpis):
        _count_row(ws, r, label, fml, banded=i % 2 == 1)
        r += 1
    r += 1

    sev_hdr = r
    _mini_header(ws, r, "Test cases by severity", "Tests")
    r += 1
    sev_first = r
    for sev in SEVERITIES:
        bg, fg = SEV_COLORS[sev]
        _count_row(ws, r, sev, f'=COUNTIF({rng(COL_SEVERITY)},"{sev}")', label_fill=bg, label_font=font(10, True, fg))
        r += 1
    sev_last = r - 1
    r += 1

    st_hdr = r
    _mini_header(ws, r, "Test cases by status", "Tests")
    r += 1
    st_first = r
    for st in STATUSES:
        bg, fg = STATUS_COLORS[st]
        _count_row(ws, r, st, f'=COUNTIF({rng(COL_STATUS)},"{st}")', label_fill=bg, label_font=font(10, True, fg))
        r += 1
    st_last = r - 1
    r += 1

    _mini_header(ws, r, "Test cases by OWASP API category (2023)", "Tests")
    r += 1
    for i, (key, (title, _desc)) in enumerate(OWASP_API.items()):
        _count_row(ws, r, f"{key}:2023  {title}", f'=COUNTIF({rng(COL_STANDARD)},"{key}:2023*")', banded=i % 2 == 1)
        r += 1
    r += 1

    cats = sorted({t.category for t in analysis.test_cases})
    _mini_header(ws, r, "Test cases by category", "Tests")
    r += 1
    for i, cat in enumerate(cats):
        crit = cat.replace('"', '""')
        _count_row(ws, r, cat, f'=COUNTIF({rng(COL_CATEGORY)},"{crit}")', banded=i % 2 == 1)
        r += 1

    _bar_chart(ws, "Test cases by severity", f"E{sev_hdr}", sev_first, sev_last, [CHART_SEV[s] for s in SEVERITIES])
    _bar_chart(ws, "Test cases by status", f"E{st_hdr + 4}", st_first, st_last, [CHART_STATUS[s] for s in STATUSES])

    # ---- disclaimer and credit (the last two rows of the sheet)
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=LAST_SUM_COL)
    _put(ws, r, 2, SAFETY_NOTE, f=font(10, True, "7A1F18"), al=Alignment(vertical="center"))
    ws.row_dimensions[r].height = 20
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=LAST_SUM_COL)
    credit = _put(ws, r, 2, f"Built by {CREDIT_NAME} | {CREDIT_URL}", f=font(10, False, TEAL, underline="single"),
                  al=Alignment(vertical="center"))
    credit.hyperlink = CREDIT_URL
    ws.row_dimensions[r].height = 20
    _print_setup(ws, f"B2:H{r}", None, generated, landscape=False)  # the cover reads best as a portrait page


# ---------------------------------------------------------------------------------------------- entry points
def build_workbook(analysis: AnalysisResult, test_case_ids: list[str] | None = None) -> bytes:
    """Build the .xlsx fully in memory and return its bytes."""
    cases = select_test_cases(analysis, test_case_ids)
    generated = date.today().isoformat()
    wb = Workbook()  # wb.active becomes the Summary sheet (first tab); the others are appended after it
    plan_last = _plan_sheet(wb, analysis, cases, generated)
    _findings_sheet(wb, analysis, generated)
    if any(f.group == "Environment" for f in analysis.findings):
        _env_sheet(wb, analysis, generated)
    _standards_sheet(wb, generated)
    _summary_sheet(wb, analysis, cases, plan_last, filtered=test_case_ids is not None, generated=generated)
    wb.calculation.fullCalcOnLoad = True
    wb.properties.title = f"{REPORT_TITLE} - {analysis.collection.name}"
    wb.properties.subject = "API security assessment test plan (static analysis; no requests sent)"
    wb.properties.creator = "API Security Test Planner"
    wb.properties.lastModifiedBy = ""
    wb.properties.keywords = "API security, OWASP API Top 10, test plan"
    wb.properties.description = SAFETY_NOTE
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_filename(analysis: AnalysisResult, filtered: bool) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", analysis.collection.name).strip("-").lower()[:40] or "collection"
    return f"api-security-test-plan-{slug}{'-filtered' if filtered else ''}-{date.today().isoformat()}.xlsx"
