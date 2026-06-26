"""Layer 2 — Technical spec extraction from row description text.

Extracts numeric specs using regex only. No LLM calls.

Input:  description string from a ParsedRow
Output: dict with typed spec fields + raw_parse_confidence (0-1)

Fields extracted:
  screen_size_inch   float | None   e.g. 65.0, 86.0, 6.5
  brightness_nit     int   | None   e.g. 350, 500
  resolution         str   | None   e.g. "3840x2160", "4K UHD", "FHD"
  response_time_ms   int   | None   e.g. 8
  work_hours         str   | None   e.g. "16/7", "24/7"
  hdmi_inputs        int   | None   e.g. 2
  camera_zoom_x      int   | None   e.g. 12
"""

import re
from typing import Any, Optional

_TOTAL_FIELDS = 7  # denominator for raw_parse_confidence


# ── Individual extractors ────────────────────────────────────────────────────

def _find_screen_size(text: str) -> Optional[float]:
    """Match: 65 אינץ' / 65 inch / 65" / 65'' """
    for pat in (
        r'(\d+(?:\.\d+)?)\s*אינץ',    # Hebrew אינץ / אינץ'
        r'(\d+(?:\.\d+)?)\s*inch',     # English
        r'(\d+(?:\.\d+)?)\s*["″]',    # 65" or 65″
        r"(\d+(?:\.\d+)?)\s*'+",       # 65'' (double apostrophe)
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def _find_brightness(text: str) -> Optional[int]:
    """Match: 350NIT / 350 NIT / 500 nit"""
    m = re.search(r'(\d+)\s*NIT', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _find_resolution(text: str) -> Optional[str]:
    """Match pixel dims (3840*2160) first, then named labels (4K UHD, FHD …)."""
    m = re.search(r'(\d{3,4})\s*[*×xX]\s*(\d{3,4})', text)
    if m:
        return f"{m.group(1)}x{m.group(2)}"
    for label in ("4K UHD", "4K", "UHD", "FHD", "HD"):
        if re.search(r'\b' + re.escape(label) + r'\b', text, re.IGNORECASE):
            return label.upper()
    return None


def _find_response_time(text: str) -> Optional[int]:
    """Match: G TO G 8MS / 8 MS / 8ms"""
    m = re.search(r'(?:G\s+TO\s+G\s+)?(\d+)\s*MS\b', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _find_work_hours(text: str) -> Optional[str]:
    """Match: 16/7 or 24/7 (common AV spec for display duty-cycle)."""
    m = re.search(r'\b((?:16|24)/7)\b', text)
    return m.group(1) if m else None


def _find_hdmi_inputs(text: str) -> Optional[int]:
    """Match: 2 כניסות HDMI (Hebrew) or HDMI x2 / HDMI x 2 (English)."""
    m = re.search(r'(\d+)\s*כניסות\s*HDMI', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'HDMI\s*[xX×]\s*(\d+)', text)
    if m:
        return int(m.group(1))
    return None


def _find_camera_zoom(text: str) -> Optional[int]:
    """Match: PTZ zoomX12 / zoomX12 / 12X zoom"""
    m = re.search(r'zoom\s*[xX×]\s*(\d+)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*[xX×]\s*zoom', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def extract_specs(description: str) -> dict[str, Any]:
    """Return specs_extracted dict for one row description.

    All seven fields are always present; missing ones are None.
    raw_parse_confidence = (fields found) / 7  — a rough signal used by
    Agent B to decide how much to trust the extracted values.
    """
    specs: dict[str, Any] = {
        "screen_size_inch":  _find_screen_size(description),
        "brightness_nit":    _find_brightness(description),
        "resolution":        _find_resolution(description),
        "response_time_ms":  _find_response_time(description),
        "work_hours":        _find_work_hours(description),
        "hdmi_inputs":       _find_hdmi_inputs(description),
        "camera_zoom_x":     _find_camera_zoom(description),
    }
    found = sum(1 for v in specs.values() if v is not None)
    specs["raw_parse_confidence"] = round(found / _TOTAL_FIELDS, 2)
    return specs


# ── Manual test: run against real parsed data ────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    path = "data/processed/proj_2026_001/parsed_contractor_a.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"{'Sheet':<40} {'Row':<4} {'sz':>4} {'nit':>4} {'res':<12} {'ms':>4} {'h/7':<5} {'hdmi':>5} {'zoom':>5} {'conf':>5}")
    print("-" * 105)

    for sheet in data["sheets"]:
        sname = sheet["sheet_name"]
        for row in sheet["rows"]:
            s = extract_specs(row["description"])
            print(
                f"{sname:<40} "
                f"{row['row_index']:<4} "
                f"{str(s['screen_size_inch'] or ''):<5}"
                f"{str(s['brightness_nit'] or ''):<5}"
                f"{(s['resolution'] or ''):<12} "
                f"{str(s['response_time_ms'] or ''):<5}"
                f"{(s['work_hours'] or ''):<6}"
                f"{str(s['hdmi_inputs'] or ''):<6}"
                f"{str(s['camera_zoom_x'] or ''):<6}"
                f"{s['raw_parse_confidence']:>4}"
            )
