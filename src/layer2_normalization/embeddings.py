"""Layer 2 — MKT similarity matching via vector embeddings.

Consumes the output of text_normalizer.normalize_file (dict with mkt_normalized
on every row) and adds a mkt_match object to each row.

Decision logic (no LLM calls):
  existing_equipment flag  →  status = existing_equipment, skip
  empty mkt_normalized     →  status = no_match
  score >= HIGH threshold  →  status = matched,   requires_agent = False
  score in [LOW, HIGH)     →  status = uncertain, requires_agent = True  → Agent A
  score <  LOW threshold   →  status = no_match,  requires_agent = False
"""

from config import settings
from src.layer2_normalization.text_normalizer import normalize_mkt
from vector_db.store import VectorStore

_METHOD_EMBEDDING = "embedding"
_METHOD_TEXT = "text_normalization"
_METHOD_NONE = "none"


def _match_row(row: dict, store: VectorStore) -> None:
    """Mutate row in-place, adding mkt_match."""
    if row["flags"]["existing_equipment"]:
        row["mkt_match"] = {
            "status": "existing_equipment",
            "matched_to": None,
            "similarity_score": None,
            "method": _METHOD_NONE,
            "requires_agent": False,
        }
        return

    mkt_normalized: str = row.get("mkt_normalized", "")

    if not mkt_normalized:
        row["mkt_match"] = {
            "status": "no_match",
            "matched_to": None,
            "similarity_score": 0.0,
            "method": _METHOD_NONE,
            "requires_agent": False,
        }
        return

    results = store.query_mkt(mkt_normalized, top_k=1)

    if not results:
        row["mkt_match"] = {
            "status": "no_match",
            "matched_to": None,
            "similarity_score": 0.0,
            "method": _METHOD_NONE,
            "requires_agent": False,
        }
        return

    top = results[0]
    score: float = top.score
    canonical: str = top.metadata.get("canonical_name", top.text)

    # Exact text match: the normalized form of the canonical name equals the query.
    method = _METHOD_TEXT if normalize_mkt(canonical) == mkt_normalized else _METHOD_EMBEDDING

    if score >= settings.SIMILARITY_THRESHOLD_HIGH:
        row["mkt_match"] = {
            "status": "matched",
            "matched_to": canonical,
            "similarity_score": round(score, 4),
            "method": method,
            "requires_agent": False,
        }
    elif score >= settings.SIMILARITY_THRESHOLD_LOW:
        row["mkt_match"] = {
            "status": "uncertain",
            "matched_to": canonical,
            "similarity_score": round(score, 4),
            "method": method,
            "requires_agent": True,
        }
    else:
        row["mkt_match"] = {
            "status": "no_match",
            "matched_to": None,
            "similarity_score": round(score, 4),
            "method": _METHOD_NONE,
            "requires_agent": False,
        }


def match_file(normalized_data: dict, store: VectorStore) -> dict:
    """Add mkt_match to every row in the normalized file dict.

    Args:
        normalized_data: output of text_normalizer.normalize_file — plain dict
                         with mkt_normalized on each row.
        store: initialised VectorStore used for similarity queries.

    Returns:
        The same dict, mutated in-place, with mkt_match added to every row.
    """
    for sheet in normalized_data["sheets"]:
        for row in sheet["rows"]:
            _match_row(row, store)
    return normalized_data
