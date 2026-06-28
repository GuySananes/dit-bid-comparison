"""Layer 3 — Agent C: contractor reference sheet.

Collects all flagged rows for a given contractor (unknown MKT, tech deviation,
math error) and produces a formal Hebrew-language letter listing corrections
required before evaluation can continue.

Output: data/output/<project_id>/ref_sheet_<contractor_id>.md
"""

import json
import logging
import os

from config.prompts import AGENT_C_SYSTEM, AGENT_C_USER
from src.utils.llm_client import call_llm

logger = logging.getLogger(__name__)

_OUTPUT_ROOT = os.path.join("data", "output")


# ── flagged-row collection ────────────────────────────────────────────────────

def _is_unknown_mkt(row: dict) -> bool:
    return row.get("mkt_match", {}).get("status") == "no_match"


def _is_tech_deviation(row: dict) -> bool:
    review = row.get("technical_review", {})
    return bool(review.get("deviation_detected")) and review.get("severity", "none") != "none"


def _is_math_error(row: dict) -> bool:
    flags = row.get("flags", {})
    if isinstance(flags, dict):
        return bool(flags.get("math_error"))
    return bool(getattr(flags, "math_error", False))


def _collect_flagged(data: dict) -> list[dict]:
    """Return one item dict per flagged row across all sheets."""
    flagged = []
    for sheet in data["sheets"]:
        sheet_name = sheet.get("sheet_name", "")
        for row in sheet["rows"]:
            issues: list[dict] = []

            if _is_unknown_mkt(row):
                match = row.get("mkt_match", {})
                issues.append({
                    "issue_type": "unknown_mkt",
                    "details": (
                        f"מק\"ט לא זוהה: {row.get('mkt_raw', '')} — "
                        f"{match.get('agent_reasoning', 'לא נמצא מוצר תואם')}"
                    ),
                })

            if _is_tech_deviation(row):
                review = row["technical_review"]
                fields = ", ".join(review.get("deviating_fields", []))
                issues.append({
                    "issue_type": "tech_deviation",
                    "details": (
                        f"חריגה טכנית ({review.get('severity', '')})"
                        + (f" בשדות: {fields}" if fields else "")
                        + f" — {review.get('reasoning', '')} "
                        f"[המלצה: {review.get('recommendation', '')}]"
                    ),
                })

            if _is_math_error(row):
                qty = row.get("quantity", "?")
                unit_price = row.get("unit_price", "?")
                total = row.get("total_price", "?")
                issues.append({
                    "issue_type": "math_error",
                    "details": (
                        f"שגיאת חשבון: {qty} × {unit_price} ≠ {total} "
                        f"(כפי שדווח בהצעה)"
                    ),
                })

            for issue in issues:
                flagged.append({
                    "row_index": row.get("row_index", "?"),
                    "sheet": sheet_name,
                    "description": row.get("description", "")[:200],
                    "issue_type": issue["issue_type"],
                    "details": issue["details"],
                })

    return flagged


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_agent(contractor_name: str, project_name: str, items: list[dict]) -> str:
    user_msg = AGENT_C_USER.format(
        contractor_name=contractor_name,
        project_name=project_name,
        items_json=json.dumps(items, ensure_ascii=False, indent=2),
    )
    response = call_llm(AGENT_C_SYSTEM, user_msg, expect_json=False)
    if not isinstance(response, str):
        raise ValueError(f"Agent C: expected string response, got {type(response)!r}")
    return response


# ── output writing ────────────────────────────────────────────────────────────

def _write_output(text: str, project_id: str, contractor_id: str) -> str:
    out_dir = os.path.join(_OUTPUT_ROOT, project_id)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"ref_sheet_{contractor_id}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    logger.info("Agent C: wrote ref sheet to %s", path)
    return path


# ── public entry point ────────────────────────────────────────────────────────

def generate_ref_sheet(data: dict) -> str | None:
    """Generate a Hebrew contractor reference sheet for all flagged rows.

    Collects rows with unknown MKT, technical deviations, or math errors,
    then calls the LLM to compose a formal correction letter.

    Args:
        data: fully-processed contractor file dict (after Agent A + B).

    Returns:
        Absolute path of the written markdown file, or None if no rows needed
        correction (nothing to write).
    """
    meta = data.get("meta", {})
    project_id = meta.get("project_id", "unknown_project")
    contractor_id = meta.get("contractor_id", "unknown_contractor")
    project_name = meta.get("project_name", project_id)
    contractor_name = meta.get("contractor_name", contractor_id)

    flagged = _collect_flagged(data)
    if not flagged:
        logger.info("Agent C: no flagged rows for %s — skipping", contractor_id)
        return None

    logger.info(
        "Agent C: %d flagged row(s) for contractor=%s project=%s",
        len(flagged), contractor_id, project_id,
    )

    letter = _call_agent(contractor_name, project_name, flagged)
    return _write_output(letter, project_id, contractor_id)
