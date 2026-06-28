"""Layer 3 — Agent D: executive summary.

Derives totals, completeness scores, and flagged deviations from the processed
contractor file dicts, then calls the LLM to write a Hebrew executive summary
for management decision-making.

Output: data/output/<project_id>/executive_summary.md
"""

from __future__ import annotations

import json
import logging
import os

from config.prompts import AGENT_D_SYSTEM, AGENT_D_USER
from src.utils.llm_client import call_llm

logger = logging.getLogger(__name__)

_OUTPUT_ROOT = os.path.join("data", "output")


# ── data derivation ───────────────────────────────────────────────────────────

def _all_sheet_names(files: list[dict]) -> list[str]:
    seen: dict[str, bool] = {}
    for f in files:
        for s in f["sheets"]:
            seen.setdefault(s["sheet_name"], True)
    return list(seen)


def _sheet_by_name(file_data: dict, name: str) -> dict | None:
    for s in file_data["sheets"]:
        if s["sheet_name"] == name:
            return s
    return None


def _all_row_indices(files: list[dict], sheet_name: str) -> set[int]:
    indices: set[int] = set()
    for f in files:
        s = _sheet_by_name(f, sheet_name)
        if s:
            for r in s["rows"]:
                indices.add(r["row_index"])
    return indices


def _sheet_total(sheet: dict | None) -> float:
    if not sheet:
        return 0.0
    total = 0.0
    for row in sheet["rows"]:
        flags = row.get("flags", {})
        not_in_total = flags.get("not_in_total") if isinstance(flags, dict) else getattr(flags, "not_in_total", False)
        if not_in_total:
            continue
        v = row.get("total_price")
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def _build_totals(files: list[dict], sheet_names: list[str]) -> dict:
    """totals[sheet_name][contractor_id] = float"""
    totals: dict[str, dict[str, float]] = {}
    for sheet_name in sheet_names:
        totals[sheet_name] = {}
        for f in files:
            cid = f["meta"]["contractor_id"]
            totals[sheet_name][cid] = _sheet_total(_sheet_by_name(f, sheet_name))
    return totals


def _build_completeness(files: list[dict], sheet_names: list[str]) -> dict:
    """completeness[contractor_id][sheet_name] = pct (0–100); also 'overall'."""
    completeness: dict[str, dict[str, float]] = {
        f["meta"]["contractor_id"]: {} for f in files
    }

    for sheet_name in sheet_names:
        all_indices = _all_row_indices(files, sheet_name)
        total = len(all_indices)
        if total == 0:
            for f in files:
                completeness[f["meta"]["contractor_id"]][sheet_name] = 0.0
            continue

        for f in files:
            cid = f["meta"]["contractor_id"]
            s = _sheet_by_name(f, sheet_name)
            filled = len({r["row_index"] for r in s["rows"]}) if s else 0
            completeness[cid][sheet_name] = round(filled / total * 100, 1)

    # Overall average across sheets
    for cid, by_sheet in completeness.items():
        scores = list(by_sheet.values())
        completeness[cid]["overall"] = round(sum(scores) / len(scores), 1) if scores else 0.0

    return completeness


def _build_deviations(files: list[dict]) -> list[dict]:
    """Collect major / disqualifying deviations across all contractors and sheets."""
    deviations: list[dict] = []
    for f in files:
        cid = f["meta"]["contractor_id"]
        for sheet in f["sheets"]:
            for row in sheet["rows"]:
                review = row.get("technical_review", {})
                severity = review.get("severity", "none")
                if severity not in ("major", "disqualifying"):
                    continue
                deviations.append({
                    "contractor": cid,
                    "sheet": sheet["sheet_name"],
                    "row_index": row.get("row_index"),
                    "description": row.get("description", "")[:150],
                    "severity": severity,
                    "reasoning": review.get("reasoning", ""),
                    "recommendation": review.get("recommendation", ""),
                })
    return deviations


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_agent(
    project_name: str,
    contractor_ids: list[str],
    sheet_names: list[str],
    totals: dict,
    completeness: dict,
    deviations: list[dict],
) -> str:
    user_msg = AGENT_D_USER.format(
        project_name=project_name,
        n_contractors=len(contractor_ids),
        room_types=", ".join(sheet_names),
        totals_json=json.dumps(totals, ensure_ascii=False, indent=2),
        completeness_json=json.dumps(completeness, ensure_ascii=False, indent=2),
        deviations_json=json.dumps(deviations, ensure_ascii=False, indent=2),
    )
    response = call_llm(AGENT_D_SYSTEM, user_msg, expect_json=False)
    if not isinstance(response, str):
        raise ValueError(f"Agent D: expected string response, got {type(response)!r}")
    return response


# ── output writing ────────────────────────────────────────────────────────────

def _write_output(text: str, project_id: str) -> str:
    out_dir = os.path.join(_OUTPUT_ROOT, project_id)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "executive_summary.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    logger.info("Agent D: executive summary written to %s", path)
    return path


# ── public entry point ────────────────────────────────────────────────────────

def generate_summary(
    contractor_files: list[dict],
    project_id: str,
    project_name: str | None = None,
) -> str:
    """Generate a Hebrew executive summary from fully-processed contractor data.

    Derives totals per room, completeness scores, and major deviations from the
    same contractor_files list passed to build_comparison_table.build().

    Args:
        contractor_files: list of data dicts (one per contractor), after all
                          Layer 2 normalisation and agent passes.
        project_id:       used for the output directory.
        project_name:     human-readable project name shown in the letter;
                          falls back to project_id if not provided.

    Returns:
        Absolute path of the written executive_summary.md file.
    """
    if not contractor_files:
        raise ValueError("generate_summary() requires at least one contractor file")

    resolved_name = project_name or project_id
    contractor_ids = [f["meta"]["contractor_id"] for f in contractor_files]
    sheet_names = _all_sheet_names(contractor_files)

    logger.info(
        "Agent D: summarising %d contractor(s), %d sheet(s) for project=%s",
        len(contractor_ids), len(sheet_names), project_id,
    )

    totals = _build_totals(contractor_files, sheet_names)
    completeness = _build_completeness(contractor_files, sheet_names)
    deviations = _build_deviations(contractor_files)

    logger.info("Agent D: %d major/disqualifying deviation(s) found", len(deviations))

    summary = _call_agent(
        resolved_name, contractor_ids, sheet_names, totals, completeness, deviations
    )
    return _write_output(summary, project_id)
