"""Build the Excel comparison table from fully-processed contractor data.

No LLM calls — pure data assembly. Matches the column layout from
"השוואת מולטימדיה לדוגמא.xlsx":

  Row 0  : title   — sheet name  |  contractor names (merged, 4 cols each)
  Row 1  : headers — # | תיאור | יחידה | כמות | הערות DIT | [per-contractor ×4]
  Row 2+ : data    — one Excel row per BOQ line item
  Last   : totals  — bold SUM per contractor (excludes not_in_total rows)

Deviation highlight rules (from technical_review.severity):
  major / disqualifying → red cell background on that contractor's 4 cells
  minor                 → yellow background
  none / missing        → no highlight
"""

import logging
import os
from typing import Optional

import xlsxwriter

logger = logging.getLogger(__name__)

# ── palette ───────────────────────────────────────────────────────────────────
_BG_TITLE = "#4472C4"    # blue — title row
_BG_HEADER = "#D9D9D9"   # gray — column headers / totals
_BG_RED = "#FFCCCC"      # light red — major/disqualifying deviation
_BG_YELLOW = "#FFFACD"   # lemon chiffon — minor deviation

# ── column layout ─────────────────────────────────────────────────────────────
_FIXED_HEADERS = ["#", "תיאור", "יחידה", "כמות", "הערות DIT"]
_CONTRACTOR_HEADERS = ['מחיר יחידה', 'סה"כ מחיר', 'יצרן + דגם', "הערות קבלן"]
_N_FIXED = len(_FIXED_HEADERS)          # 5
_N_PER_CONTRACTOR = len(_CONTRACTOR_HEADERS)  # 4


# ── helpers — data navigation ─────────────────────────────────────────────────

def _sheet_by_name(file_data: dict, name: str) -> Optional[dict]:
    for s in file_data["sheets"]:
        if s["sheet_name"] == name:
            return s
    return None


def _row_by_index(sheet: dict, idx: int) -> Optional[dict]:
    for r in sheet["rows"]:
        if r["row_index"] == idx:
            return r
    return None


def _all_sheet_names(files: list[dict]) -> list[str]:
    """Ordered unique sheet names across all contractor files."""
    seen: dict[str, bool] = {}
    for f in files:
        for s in f["sheets"]:
            seen.setdefault(s["sheet_name"], True)
    return list(seen)


def _sorted_row_indices(files: list[dict], sheet_name: str) -> list[int]:
    """Union of row indices across all contractors for one sheet, sorted."""
    indices: set[int] = set()
    for f in files:
        s = _sheet_by_name(f, sheet_name)
        if s:
            for r in s["rows"]:
                indices.add(r["row_index"])
    return sorted(indices)


def _reference_row(files: list[dict], sheet_name: str, idx: int) -> Optional[dict]:
    """First available row for (sheet, idx) — used for description/unit/qty."""
    for f in files:
        s = _sheet_by_name(f, sheet_name)
        if s:
            r = _row_by_index(s, idx)
            if r:
                return r
    return None


# ── helpers — deviation severity ──────────────────────────────────────────────

def _severity(row: dict) -> str:
    return row.get("technical_review", {}).get("severity", "none")


def _deviation_bg(row: dict) -> Optional[str]:
    sev = _severity(row)
    if sev in ("major", "disqualifying"):
        return _BG_RED
    if sev == "minor":
        return _BG_YELLOW
    return None


# ── helpers — numeric total ───────────────────────────────────────────────────

def _numeric_total(row: dict) -> Optional[float]:
    if row["flags"]["not_in_total"]:
        return None
    v = row.get("total_price")
    return float(v) if isinstance(v, (int, float)) else None


# ── format factory ────────────────────────────────────────────────────────────

def _make_formats(wb: xlsxwriter.Workbook) -> dict:
    def _base(**kw):
        return {"border": 1, "valign": "top", **kw}

    return {
        "title": wb.add_format({
            "bold": True, "font_size": 11,
            "bg_color": _BG_TITLE, "font_color": "white",
            "align": "center", "valign": "vcenter", "border": 1,
        }),
        "header": wb.add_format({
            "bold": True, "bg_color": _BG_HEADER, "border": 1,
            "align": "center", "valign": "vcenter", "text_wrap": True,
        }),
        "total_label": wb.add_format({
            "bold": True, "bg_color": _BG_HEADER, "border": 1,
            "align": "right",
        }),
        "total_num": wb.add_format({
            "bold": True, "bg_color": _BG_HEADER, "border": 1,
            "num_format": '#,##0',
        }),
        # data — plain
        "data": wb.add_format(_base(text_wrap=True)),
        "data_num": wb.add_format(_base(num_format='#,##0')),
        # data — not-in-total (greyed italic)
        "not_counted": wb.add_format(_base(
            font_color="#777777", italic=True, text_wrap=True,
        )),
        # data — red deviation
        "red": wb.add_format(_base(bg_color=_BG_RED, text_wrap=True)),
        "red_num": wb.add_format(_base(bg_color=_BG_RED, num_format='#,##0')),
        # data — yellow deviation
        "yellow": wb.add_format(_base(bg_color=_BG_YELLOW, text_wrap=True)),
        "yellow_num": wb.add_format(_base(bg_color=_BG_YELLOW, num_format='#,##0')),
    }


def _pick_fmt(fmts: dict, bg: Optional[str], numeric: bool, not_counted: bool) -> object:
    if not_counted:
        return fmts["not_counted"]
    if bg == _BG_RED:
        return fmts["red_num"] if numeric else fmts["red"]
    if bg == _BG_YELLOW:
        return fmts["yellow_num"] if numeric else fmts["yellow"]
    return fmts["data_num"] if numeric else fmts["data"]


# ── sheet writer ──────────────────────────────────────────────────────────────

def _write_sheet(
    ws,
    sheet_name: str,
    files: list[dict],
    contractor_ids: list[str],
    fmts: dict,
) -> None:
    n = len(contractor_ids)

    # ── column widths ─────────────────────────────────────────────────────────
    ws.right_to_left()
    ws.set_column(0, 0, 5)    # #
    ws.set_column(1, 1, 46)   # description
    ws.set_column(2, 2, 8)    # unit
    ws.set_column(3, 3, 6)    # qty
    ws.set_column(4, 4, 20)   # DIT notes
    for i in range(n):
        b = _N_FIXED + i * _N_PER_CONTRACTOR
        ws.set_column(b, b, 12)         # unit price
        ws.set_column(b + 1, b + 1, 12) # total
        ws.set_column(b + 2, b + 2, 22) # model
        ws.set_column(b + 3, b + 3, 18) # contractor notes
    ws.set_row(0, 22)
    ws.set_row(1, 36)

    # ── row 0: title ──────────────────────────────────────────────────────────
    last_col = _N_FIXED + n * _N_PER_CONTRACTOR - 1
    ws.merge_range(0, 0, 0, _N_FIXED - 1, sheet_name, fmts["title"])
    for i, cid in enumerate(contractor_ids):
        b = _N_FIXED + i * _N_PER_CONTRACTOR
        ws.merge_range(0, b, 0, b + _N_PER_CONTRACTOR - 1, cid, fmts["title"])

    # ── row 1: column headers ─────────────────────────────────────────────────
    for col, hdr in enumerate(_FIXED_HEADERS):
        ws.write(1, col, hdr, fmts["header"])
    for i in range(n):
        b = _N_FIXED + i * _N_PER_CONTRACTOR
        for j, hdr in enumerate(_CONTRACTOR_HEADERS):
            ws.write(1, b + j, hdr, fmts["header"])

    # ── data rows ─────────────────────────────────────────────────────────────
    row_indices = _sorted_row_indices(files, sheet_name)
    excel_row = 2
    contractor_totals = [0.0] * n

    for idx in row_indices:
        ref = _reference_row(files, sheet_name, idx)
        if not ref:
            continue

        # Fixed columns
        ws.write(excel_row, 0, idx, fmts["data"])
        ws.write(excel_row, 1, ref.get("description", ""), fmts["data"])
        ws.write(excel_row, 2, ref.get("unit", ""), fmts["data"])
        qty = ref.get("quantity")
        if isinstance(qty, (int, float)):
            ws.write_number(excel_row, 3, qty, fmts["data_num"])
        else:
            ws.write(excel_row, 3, str(qty) if qty is not None else "", fmts["data"])
        ws.write(excel_row, 4, "", fmts["data"])  # DIT notes — populated manually by PM

        # Per-contractor columns
        for i, f in enumerate(files):
            b = _N_FIXED + i * _N_PER_CONTRACTOR
            s = _sheet_by_name(f, sheet_name)
            row = _row_by_index(s, idx) if s else None

            if not row:
                for j in range(_N_PER_CONTRACTOR):
                    ws.write(excel_row, b + j, "", fmts["data"])
                continue

            bg = _deviation_bg(row)
            not_counted = bool(row["flags"]["not_in_total"])

            # unit_price
            up = row.get("unit_price")
            if isinstance(up, (int, float)):
                ws.write_number(excel_row, b, up, _pick_fmt(fmts, bg, True, False))
            else:
                ws.write(excel_row, b, str(up) if up else "", _pick_fmt(fmts, bg, False, False))

            # total_price
            tp = row.get("total_price")
            if not_counted:
                ws.write(excel_row, b + 1, "לא לסיכום", fmts["not_counted"])
            elif isinstance(tp, (int, float)):
                ws.write_number(excel_row, b + 1, tp, _pick_fmt(fmts, bg, True, False))
                contractor_totals[i] += tp
            else:
                ws.write(excel_row, b + 1, str(tp) if tp else "", _pick_fmt(fmts, bg, False, False))

            # model — prepend marker if MKT was unrecognised
            model = row.get("manufacturer_model", "")
            if row.get("mkt_match", {}).get("status") == "no_match" and model:
                model = f"[?] {model}"
            ws.write(excel_row, b + 2, model, _pick_fmt(fmts, bg, False, False))

            # contractor notes
            ws.write(excel_row, b + 3, row.get("notes", ""), _pick_fmt(fmts, bg, False, False))

        excel_row += 1

    # ── totals row ────────────────────────────────────────────────────────────
    ws.write(excel_row, 0, "", fmts["total_num"])
    ws.write(excel_row, 1, 'סה"כ', fmts["total_label"])
    for col in range(2, _N_FIXED):
        ws.write(excel_row, col, "", fmts["total_num"])
    for i in range(n):
        b = _N_FIXED + i * _N_PER_CONTRACTOR
        ws.write(excel_row, b, "", fmts["total_num"])
        ws.write_number(excel_row, b + 1, contractor_totals[i], fmts["total_num"])
        ws.write(excel_row, b + 2, "", fmts["total_num"])
        ws.write(excel_row, b + 3, "", fmts["total_num"])


# ── public entry point ────────────────────────────────────────────────────────

def build(
    contractor_files: list[dict],
    project_id: str,
    output_dir: str = "./data/output",
) -> str:
    """Build comparison Excel from fully-processed contractor file dicts.

    Args:
        contractor_files: list of data dicts (one per contractor) after all
                          Layer 2 normalisation and agent passes.
        project_id:       used for the output filename and directory.
        output_dir:       root output directory (default: ./data/output).

    Returns:
        Absolute path to the written .xlsx file.
    """
    if not contractor_files:
        raise ValueError("build() requires at least one contractor file")

    out_dir = os.path.join(output_dir, project_id)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"comparison_{project_id}.xlsx")

    contractor_ids = [f["meta"]["contractor_id"] for f in contractor_files]

    wb = xlsxwriter.Workbook(out_path, {"strings_to_numbers": False})
    fmts = _make_formats(wb)

    sheet_names = _all_sheet_names(contractor_files)
    logger.info("Building comparison table: %d sheet(s), %d contractor(s)",
                len(sheet_names), len(contractor_ids))

    for sheet_name in sheet_names:
        # Excel sheet names must be ≤ 31 characters and cannot contain / \ ? * [ ]
        safe_name = sheet_name[:31].translate(str.maketrans("/\\?*[]", "------"))
        ws = wb.add_worksheet(safe_name)
        _write_sheet(ws, sheet_name, contractor_files, contractor_ids, fmts)
        logger.info("  sheet written: %r", sheet_name)

    wb.close()
    logger.info("Comparison table saved: %s", out_path)
    return out_path
