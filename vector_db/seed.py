"""Seed the approved_mkts collection from curated CSV and/or parsed contractor JSONs.

Usage:
    py vector_db/seed.py                  # both sources
    py vector_db/seed.py --from-csv       # CSV only
    py vector_db/seed.py --from-parsed    # contractor JSONs only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# Make imports work when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.layer2_normalization.text_normalizer import normalize_mkt
from vector_db.store import VectorStore

CSV_PATH = Path("data/seed/known_mkts.csv")
PARSED_DIR = Path("data/processed/proj_2026_001")
CONTRACTOR_FILES = ["parsed_contractor_a.json", "parsed_contractor_b.json"]


# ── CSV source ────────────────────────────────────────────────────────────────

def seed_from_csv(store: VectorStore) -> int:
    """Seed from data/seed/known_mkts.csv. Returns number of entries added."""
    if not CSV_PATH.exists():
        print(f"  [csv] {CSV_PATH} not found — skipping.")
        return 0

    count = 0
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = row["canonical_name"].strip()
            if not canonical:
                continue

            raw_aliases = row.get("aliases", "")
            aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]

            metadata = {}
            if row.get("brand"):
                metadata["brand"] = row["brand"].strip()
            if row.get("category"):
                metadata["category"] = row["category"].strip()
            metadata["source"] = "seed_csv"
            metadata["approved"] = True

            store.add_mkt(canonical, aliases, metadata)
            count += 1

    return count


# ── Parsed contractor JSON source ─────────────────────────────────────────────

def _iter_rows(file_path: Path):
    with file_path.open(encoding="utf-8") as f:
        data = json.load(f)
    for sheet in data.get("sheets", []):
        for row in sheet.get("rows", []):
            yield row


def seed_from_parsed(store: VectorStore) -> int:
    """Extract unique manufacturer_model values from contractor JSONs. Returns count."""
    seen_normalized: dict[str, str] = {}  # normalized → first raw string seen

    for filename in CONTRACTOR_FILES:
        path = PARSED_DIR / filename
        if not path.exists():
            print(f"  [parsed] {path} not found — skipping.")
            continue

        for row in _iter_rows(path):
            raw = (row.get("manufacturer_model") or row.get("mkt_raw") or "").strip()
            if not raw:
                continue
            normalized = normalize_mkt(raw)
            if normalized and normalized not in seen_normalized:
                seen_normalized[normalized] = raw

    if not seen_normalized:
        print("  [parsed] No manufacturer_model values found.")
        return 0

    for normalized, raw in seen_normalized.items():
        aliases = [raw] if raw.lower() != normalized else []
        store.add_mkt(
            canonical_name=normalized,
            aliases=aliases,
            metadata={
                "source": "parsed_contractor_json",
                "project_id": PARSED_DIR.name,
                "approved": False,  # extracted from raw data, not manually curated
            },
        )

    return len(seen_normalized)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the VectorStore approved_mkts collection.")
    parser.add_argument("--from-csv", action="store_true", help="Seed from CSV only")
    parser.add_argument("--from-parsed", action="store_true", help="Seed from contractor JSONs only")
    args = parser.parse_args()

    run_csv = args.from_csv or (not args.from_csv and not args.from_parsed)
    run_parsed = args.from_parsed or (not args.from_csv and not args.from_parsed)

    print("Initialising VectorStore…")
    store = VectorStore()

    csv_count = parsed_count = 0

    if run_csv:
        print("Seeding from CSV…")
        csv_count = seed_from_csv(store)
        print(f"  [csv] {csv_count} entries added/updated.")

    if run_parsed:
        print("Seeding from contractor JSONs…")
        parsed_count = seed_from_parsed(store)
        print(f"  [parsed] {parsed_count} unique MKTs added/updated.")

    total = csv_count + parsed_count
    print(f"\nDone. Total entries added/updated: {total}")


if __name__ == "__main__":
    main()
