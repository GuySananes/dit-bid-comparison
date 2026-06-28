"""Layer 3 — Agent A: ambiguity resolution for uncertain MKT matches.

Collects all rows where mkt_match.requires_agent == True, sends them in
batches to the LLM, and updates mkt_match with the agent's decision.

High/medium confidence same-product decisions are written back to VectorStore
so the same pair resolves automatically next time without an LLM call.
"""

import json
import logging

from config.prompts import AGENT_A_BATCH_USER, AGENT_A_SYSTEM
from src.utils.llm_client import call_llm
from vector_db.store import VectorStore

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20  # max pairs per LLM call


# ── data collection ───────────────────────────────────────────────────────────

def _collect_uncertain(data: dict) -> list[dict]:
    """Return list of {si, ri, row} for rows where mkt_match.requires_agent."""
    hits = []
    for si, sheet in enumerate(data["sheets"]):
        for ri, row in enumerate(sheet["rows"]):
            if row.get("mkt_match", {}).get("requires_agent"):
                hits.append({"si": si, "ri": ri, "row": row})
    return hits


def _build_pair(entry: dict, idx: int) -> dict:
    row = entry["row"]
    match = row["mkt_match"]
    return {
        "index": idx,
        "mkt_a": match.get("matched_to") or "",
        "mkt_b": row.get("manufacturer_model") or row.get("mkt_raw") or row.get("mkt_normalized") or "",
        "similarity_score": match.get("similarity_score") or 0.0,
        "context": "",
    }


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_batch(pairs: list[dict]) -> list[dict]:
    user_msg = AGENT_A_BATCH_USER.format(
        pairs_json=json.dumps(pairs, ensure_ascii=False, indent=2)
    )
    response = call_llm(AGENT_A_SYSTEM, user_msg, expect_json=True)

    if isinstance(response, list):
        return response

    # Some models wrap the array in a dict key — unwrap defensively
    if isinstance(response, dict):
        for val in response.values():
            if isinstance(val, list):
                return val

    raise ValueError(f"Agent A: unexpected LLM response shape: {type(response)!r}")


# ── row update ────────────────────────────────────────────────────────────────

def _apply_decision(row: dict, decision: dict) -> None:
    is_same = bool(decision.get("is_same_product"))
    confidence = decision.get("confidence", "low")
    normalized = decision.get("normalized_name") or row["mkt_match"].get("matched_to") or ""

    row["mkt_match"].update({
        "status": "matched" if is_same else "no_match",
        "matched_to": normalized if is_same else None,
        "method": "agent_a",
        "agent_reasoning": decision.get("reasoning", ""),
        "agent_confidence": confidence,
        "requires_agent": False,
    })


# ── learning loop ─────────────────────────────────────────────────────────────

def _learn(row: dict, decision: dict, store: VectorStore) -> None:
    """Write same-product decisions with high/medium confidence to VectorStore."""
    if decision.get("confidence") not in ("high", "medium"):
        return
    if not decision.get("is_same_product"):
        return

    canonical = decision.get("normalized_name", "").strip()
    alias = (
        row.get("manufacturer_model")
        or row.get("mkt_raw")
        or row.get("mkt_normalized")
        or ""
    ).strip()

    if not canonical or not alias or alias == canonical:
        return

    store.add_mkt(
        canonical_name=canonical,
        aliases=[alias],
        metadata={"source": "agent_a", "confidence": decision["confidence"]},
    )
    logger.info("VectorStore updated: canonical=%r  alias=%r", canonical, alias)


# ── public entry point ────────────────────────────────────────────────────────

def resolve_ambiguities(data: dict, store: VectorStore) -> dict:
    """Resolve all rows with mkt_match.requires_agent=True via LLM.

    Sends uncertain pairs in batches of up to _BATCH_SIZE to minimise API calls.
    Updates data in-place and returns it.

    Args:
        data:  the normalized file dict produced by text_normalizer + embeddings.
        store: initialised VectorStore used for the learning-loop writes.
    """
    uncertain = _collect_uncertain(data)
    if not uncertain:
        logger.info("Agent A: no uncertain rows — skipping")
        return data

    logger.info("Agent A: resolving %d uncertain row(s)", len(uncertain))

    for batch_start in range(0, len(uncertain), _BATCH_SIZE):
        batch = uncertain[batch_start: batch_start + _BATCH_SIZE]
        pairs = [_build_pair(entry, i) for i, entry in enumerate(batch)]

        decisions = _call_batch(pairs)
        by_index: dict[int, dict] = {int(d["index"]): d for d in decisions}

        for i, entry in enumerate(batch):
            decision = by_index.get(i)
            if decision is None:
                logger.warning("Agent A: no decision returned for batch item %d", i)
                continue

            row = entry["row"]
            _apply_decision(row, decision)
            _learn(row, decision, store)

            # Write back into the shared data dict
            data["sheets"][entry["si"]]["rows"][entry["ri"]] = row

    return data
