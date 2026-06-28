"""DIT Bid Comparison Pipeline — orchestrator.

Runs all three layers in order for every contractor file found in --input,
saves intermediate JSON at each stage, and produces:
  - comparison_<project>.xlsx       (Layer 3, build_comparison_table)
  - ref_sheet_<contractor>.md       (Agent C, per contractor)
  - executive_summary.md            (Agent D)

Usage:
    py main.py --input data/raw/ --boq data/raw/boq.xlsx --project proj_2026_001
    py main.py --input data/raw/ --boq data/raw/boq.xlsx --project proj_2026_001 \\
               --project-name "פרויקט מולטימדיה 2026"

VectorStore write-back:
    Agent A writes matched MKT pairs back during resolve_ambiguities().
    Agent B writes positive deviation rulings during review_file().
    Both happen incrementally so each subsequent contractor benefits immediately.
"""

import argparse
import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path

from src.layer1_parser.excel_reader import parse_excel
from src.layer2_normalization.embeddings import match_file
from src.layer2_normalization.math_validator import validate_file
from src.layer2_normalization.spec_extractor import extract_specs
from src.layer2_normalization.text_normalizer import normalize_mkt
from src.layer3_agents.agent_a_ambiguity import resolve_ambiguities
from src.layer3_agents.agent_b_deviation import review_file
from src.layer3_agents.agent_c_ref_sheet import generate_ref_sheet
from src.layer3_agents.agent_d_summary import generate_summary
from src.layer3_agents.build_comparison_table import build
from vector_db.store import VectorStore

# ── logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

# ── constants ─────────────────────────────────────────────────────────────────

_PROCESSED_ROOT = Path("data/processed")


# ── helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def _step(label: str):
    """Log step start/end with wall-clock timing."""
    logger.info("▶  %s", label)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        logger.info("✓  %s  (%.1fs)", label, time.perf_counter() - t0)


def _save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.debug("saved %s", path)


def _contractor_id(path: Path) -> str:
    """Derive a filesystem-safe ASCII contractor_id from a filename stem."""
    stem = path.stem.replace(" ", "_")
    safe = "".join(
        c if (c.isascii() and (c.isalnum() or c in "_-")) else "_"
        for c in stem
    )
    return safe.strip("_") or "contractor"


def _discover_contractors(input_dir: Path, boq_path: Path) -> list[Path]:
    """Return all .xlsx files in input_dir that are not the BOQ, sorted."""
    boq_resolved = boq_path.resolve() if boq_path.exists() else None
    return sorted(
        p for p in input_dir.glob("*.xlsx")
        if p.resolve() != boq_resolved
    )


# ── per-contractor pipeline ───────────────────────────────────────────────────

def _apply_layer2(parsed_file, store: VectorStore) -> dict:
    """Run all Layer 2 transforms on a ParsedFile; return enriched dict."""
    # math_validator starts from the Pydantic model → plain dict with flags populated
    data = validate_file(parsed_file)

    # Add mkt_normalized + specs_extracted per row (pure regex, no LLM)
    for sheet in data["sheets"]:
        for row in sheet["rows"]:
            raw = row.get("manufacturer_model") or row.get("mkt_raw") or ""
            row["mkt_normalized"] = normalize_mkt(raw)
            row["specs_extracted"] = extract_specs(row["description"])

    # Vector similarity matching — adds mkt_match to every row
    match_file(data, store)
    return data


def process_contractor(xlsx_path: Path, project_id: str, store: VectorStore) -> dict:
    """Run Layers 1–2 and Agents A–B for one contractor file.

    Saves intermediate JSON after Layer 1, after Layer 2, and after both
    agents complete.  Returns the fully reviewed data dict.
    """
    cid = _contractor_id(xlsx_path)
    proc_dir = _PROCESSED_ROOT / project_id
    tag = f"[{cid}]"

    # ── Layer 1 ──────────────────────────────────────────────────────────────
    with _step(f"{tag} Layer 1 — parse Excel"):
        parsed = parse_excel(xlsx_path, cid, project_id)

    _save_json(
        json.loads(parsed.model_dump_json()),   # datetime → ISO string via Pydantic
        proc_dir / f"parsed_{cid}.json",
    )
    logger.info("%s parsed %d sheet(s)", tag, len(parsed.sheets))

    # ── Layer 2 ──────────────────────────────────────────────────────────────
    with _step(f"{tag} Layer 2 — normalize / specs / math / embeddings"):
        data = _apply_layer2(parsed, store)

    _save_json(data, proc_dir / f"normalized_{cid}.json")

    n_math = sum(
        1 for s in data["sheets"] for r in s["rows"]
        if r.get("flags", {}).get("math_error")
    )
    n_uncertain = sum(
        1 for s in data["sheets"] for r in s["rows"]
        if r.get("mkt_match", {}).get("requires_agent")
    )
    logger.info("%s math_errors=%d  uncertain_mkts=%d", tag, n_math, n_uncertain)

    # ── Agent A — MKT ambiguity resolution ───────────────────────────────────
    with _step(f"{tag} Agent A — resolve MKT ambiguities"):
        data = resolve_ambiguities(data, store)

    # ── Agent B — technical deviation review ─────────────────────────────────
    with _step(f"{tag} Agent B — technical deviation review"):
        data = review_file(data, store)

    _save_json(data, proc_dir / f"reviewed_{cid}.json")

    n_deviations = sum(
        1 for s in data["sheets"] for r in s["rows"]
        if r.get("technical_review", {}).get("deviation_detected")
    )
    logger.info("%s deviations_found=%d", tag, n_deviations)

    return data


# ── pipeline orchestrator ─────────────────────────────────────────────────────

def run_pipeline(
    input_dir: Path,
    boq_path: Path,
    project_id: str,
    project_name: str | None,
) -> None:
    t_total = time.perf_counter()

    logger.info("=" * 64)
    logger.info("DIT Bid Comparison — project: %s", project_id)
    logger.info("=" * 64)

    with _step("Init VectorStore"):
        store = VectorStore()

    contractor_paths = _discover_contractors(input_dir, boq_path)
    if not contractor_paths:
        raise SystemExit(f"No contractor Excel files found in {input_dir}")
    logger.info(
        "Contractors found (%d): %s",
        len(contractor_paths),
        [p.name for p in contractor_paths],
    )

    # Process sequentially so Agent A/B write-backs accumulate across contractors
    contractor_data: list[dict] = []
    for path in contractor_paths:
        data = process_contractor(path, project_id, store)
        contractor_data.append(data)

    # ── Layer 3 outputs ───────────────────────────────────────────────────────

    with _step("Build comparison table (Excel)"):
        xlsx_out = build(contractor_data, project_id)
    logger.info("Comparison table → %s", xlsx_out)

    for data in contractor_data:
        cid = data["meta"]["contractor_id"]
        with _step(f"[{cid}] Agent C — contractor ref sheet"):
            ref_path = generate_ref_sheet(data)
        if ref_path:
            logger.info("[%s] Ref sheet → %s", cid, ref_path)
        else:
            logger.info("[%s] No flagged items — ref sheet skipped", cid)

    with _step("Agent D — executive summary"):
        summary_path = generate_summary(contractor_data, project_id, project_name)
    logger.info("Executive summary → %s", summary_path)

    logger.info("=" * 64)
    logger.info("Pipeline complete — %.1fs total", time.perf_counter() - t_total)
    logger.info("=" * 64)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DIT Bid Comparison Pipeline — compare contractor bids against a BOQ.",
    )
    parser.add_argument(
        "--input", required=True,
        help="Directory containing contractor Excel files (.xlsx)",
    )
    parser.add_argument(
        "--boq", required=True,
        help="Path to the BOQ Excel file (excluded from contractor processing)",
    )
    parser.add_argument(
        "--project", required=True,
        help="Project identifier used for output folders (e.g. proj_2026_001)",
    )
    parser.add_argument(
        "--project-name", default=None,
        help="Human-readable project name shown in reports (Hebrew OK)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    boq_path = Path(args.boq)

    if not input_dir.is_dir():
        raise SystemExit(f"--input is not a directory: {input_dir}")
    if not boq_path.exists():
        logger.warning(
            "BOQ file not found: %s — BOQ parsing is reserved for a future step, continuing.",
            boq_path,
        )

    run_pipeline(input_dir, boq_path, args.project, args.project_name)


if __name__ == "__main__":
    main()
