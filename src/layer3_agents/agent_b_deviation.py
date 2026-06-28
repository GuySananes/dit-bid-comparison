"""Layer 3 — Agent B: technical deviation review.

For each row whose spec_extractor returned raw_parse_confidence > 0.0:
  1. Query VectorStore for past rulings on similar deviations (RAG).
  2. Call LLM to evaluate whether the contractor's offer meets the BOQ spec.
  3. Write the decision back to VectorStore for future projects.

Batches all eligible rows within a sheet into a single LLM call to reduce cost.
"""

import json
import logging

from config.prompts import AGENT_B_BATCH_USER, AGENT_B_SYSTEM
from src.layer2_normalization.spec_extractor import extract_specs
from src.utils.llm_client import call_llm
from vector_db.store import VectorStore

logger = logging.getLogger(__name__)

# Specs that are purely pipeline bookkeeping — never sent to the LLM
_META_KEYS = frozenset({"raw_parse_confidence"})


# ── eligibility ───────────────────────────────────────────────────────────────

def _is_eligible(row: dict) -> bool:
    return row.get("specs_extracted", {}).get("raw_parse_confidence", 0.0) > 0.0


# ── item construction ─────────────────────────────────────────────────────────

def _boq_specs(row: dict) -> dict:
    return {
        k: v
        for k, v in row.get("specs_extracted", {}).items()
        if k not in _META_KEYS and v is not None
    }


def _contractor_specs(row: dict) -> dict:
    contractor_text = " ".join(filter(None, [
        row.get("manufacturer_model", ""),
        row.get("notes", ""),
    ]))
    raw = extract_specs(contractor_text)
    return {k: v for k, v in raw.items() if k not in _META_KEYS and v is not None}


def _rag_query(row: dict, store: VectorStore) -> tuple[str, list[str]]:
    """Build a RAG query from the row's description and return (context_text, source_ids)."""
    # Lean on the most distinctive part of the description — first 120 chars
    query = row.get("description", "")[:120]
    results = store.query_decisions(query, top_k=3)
    if not results:
        return "No prior rulings.", []
    context = "\n".join(f"[{r.id}] {r.text}" for r in results)
    source_ids = [r.id for r in results]
    return context, source_ids


def _build_item(row: dict, idx: int, store: VectorStore) -> dict:
    rag_context, rag_ids = _rag_query(row, store)
    return {
        "index": idx,
        "boq_description": row.get("description", "")[:400],
        "boq_specs": _boq_specs(row),
        "contractor_description": " | ".join(filter(None, [
            row.get("manufacturer_model", ""),
            row.get("notes", ""),
        ])),
        "contractor_specs": _contractor_specs(row),
        "rag_context": rag_context,
        "_rag_source_ids": rag_ids,  # internal — stripped before sending to LLM
    }


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_batch(items: list[dict]) -> list[dict]:
    # Strip internal bookkeeping keys before serialising for the LLM
    clean = [{k: v for k, v in it.items() if not k.startswith("_")} for it in items]
    user_msg = AGENT_B_BATCH_USER.format(
        items_json=json.dumps(clean, ensure_ascii=False, indent=2)
    )
    response = call_llm(AGENT_B_SYSTEM, user_msg, expect_json=True)

    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for val in response.values():
            if isinstance(val, list):
                return val
    raise ValueError(f"Agent B: unexpected LLM response shape: {type(response)!r}")


# ── result formatting ─────────────────────────────────────────────────────────

def _format_technical_review(decision: dict, item: dict) -> dict:
    return {
        "deviation_detected": bool(decision.get("deviation_detected")),
        "severity": decision.get("severity", "none"),
        "deviating_fields": decision.get("deviating_fields", []),
        "reasoning": decision.get("reasoning", ""),
        "recommendation": decision.get("recommendation", "accept"),
        "rag_sources_used": decision.get("rag_sources_used") or item.get("_rag_source_ids", []),
    }


# ── VectorStore write-back ────────────────────────────────────────────────────

def _store_decision(row: dict, review: dict, meta: dict, store: VectorStore) -> None:
    if not review.get("deviation_detected"):
        return  # only store positive deviation rulings

    severity = review.get("severity", "none")
    if severity == "none":
        return

    # Compose a searchable text summary of the ruling
    description_snippet = row.get("description", "")[:100]
    model = row.get("manufacturer_model", "?")
    boq_specs = _boq_specs(row)
    contractor_specs_text = json.dumps(_contractor_specs(row), ensure_ascii=False)
    reasoning = review.get("reasoning", "")

    text = (
        f"Project {meta.get('project_id', '?')} | "
        f"BOQ: {description_snippet} | "
        f"Spec required: {boq_specs} | "
        f"Contractor offered: {model} | Specs: {contractor_specs_text} | "
        f"Severity: {severity} | Ruling: {reasoning}"
    )

    store.add_decision({
        "text": text,
        "project_id": meta.get("project_id", ""),
        "contractor_id": meta.get("contractor_id", ""),
        "severity": severity,
        "recommendation": review.get("recommendation", ""),
    })
    logger.info("VectorStore decision stored: severity=%s contractor=%s",
                severity, meta.get("contractor_id"))


# ── sheet-level orchestration ─────────────────────────────────────────────────

def _review_sheet(sheet: dict, meta: dict, store: VectorStore) -> None:
    eligible = [(i, row) for i, row in enumerate(sheet["rows"]) if _is_eligible(row)]
    if not eligible:
        return

    logger.info("Agent B: sheet=%r reviewing %d row(s)", sheet["sheet_name"], len(eligible))

    items = [_build_item(row, idx, store) for idx, (_, row) in enumerate(eligible)]
    decisions = _call_batch(items)
    by_index: dict[int, dict] = {int(d["index"]): d for d in decisions}

    for local_idx, (_, row) in enumerate(eligible):
        decision = by_index.get(local_idx)
        if decision is None:
            logger.warning("Agent B: no decision for item %d in sheet %r",
                           local_idx, sheet["sheet_name"])
            continue

        review = _format_technical_review(decision, items[local_idx])
        row["technical_review"] = review
        _store_decision(row, review, meta, store)


# ── public entry point ────────────────────────────────────────────────────────

def review_file(data: dict, store: VectorStore) -> dict:
    """Add technical_review to every eligible row in the processed file dict.

    Eligibility: row must have specs_extracted.raw_parse_confidence > 0.0.
    Batches per sheet to minimise LLM API calls.

    Args:
        data:  fully-processed contractor file dict (after Layer 2 + Agent A).
        store: initialised VectorStore for RAG queries and decision write-back.

    Returns:
        The same dict, mutated in-place, with technical_review on eligible rows.
    """
    meta = data.get("meta", {})
    for sheet in data["sheets"]:
        _review_sheet(sheet, meta, store)
    return data
