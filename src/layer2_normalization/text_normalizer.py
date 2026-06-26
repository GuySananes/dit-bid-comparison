"""Layer 2 — MKT string normalization.

Converts raw manufacturer_model strings into a canonical form so that
variations of the same product become identical strings for exact matching.

No LLM calls. Pure string rules + regex.
"""

import copy
import re

from src.layer1_parser.schema import ParsedFile


# ── Noise words to strip (decorative words that add no identity) ────────────
NOISE_WORDS: frozenset[str] = frozenset({
    "studio", "professional", "series", "kit", "bundle", "black",
    "touch", "controller", "glass", "mount", "celling", "ceiling",
    "table", "vc", "system", "ex", "plus", "new", "poe",
})

# ── Brand aliases: normalize spelling variants ───────────────────────────────
BRAND_ALIASES: dict[str, str] = {
    "polycom": "poly",
}

# ── Poly accessories: stripped when a codec model (X/G series) is present ───
POLY_ACCESSORIES: frozenset[str] = frozenset({
    "tc10", "tc8", "mic", "mics", "bridge",
})


def _basic_normalize(raw: str) -> str:
    """Steps 1-6: lowercase, strip specials, collapse spaces, apply aliases."""
    # Multiline manufacturer_model: take first meaningful line only
    text = raw.split("\n")[0].strip()

    # 1. Lowercase
    text = text.lower()

    # 2-3. Remove special characters, replacing with space
    text = re.sub(r'[-/+."\'()*@#]', " ", text)

    # 4. Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    # 6. Brand aliases (applied before noise removal so "polycom studio" → "poly studio")
    for alias, canonical in BRAND_ALIASES.items():
        text = re.sub(r"\b" + re.escape(alias) + r"\b", canonical, text)

    return text


def _normalize_poly_bundle(tokens: list[str]) -> str:
    """Step 7: extract core Poly codec from a bundle token list.

    Priority: X-series codec > G-series codec > TC-series controller.
    When the core model is found, all accessories and noise are discarded.
    """
    # X-series codecs (X52, X32, X72, …)
    for t in tokens:
        m = re.match(r"^x(\d+)$", t)
        if m:
            return "polyx" + m.group(1)

    # G-series codecs (G62, G7500, …)
    for t in tokens:
        m = re.match(r"^g(\d+)$", t)
        if m:
            return "polyg" + m.group(1)

    # TC-series controllers — standalone product, not a bundle accessory
    for t in tokens:
        m = re.match(r"^tc(\d+)$", t)
        if m:
            return "polytc" + m.group(1)

    # Fallback: join all non-accessory, non-noise poly tokens
    kept = [
        t for t in tokens
        if t not in POLY_ACCESSORIES and t not in NOISE_WORDS and t != "poly"
    ]
    return "poly" + "".join(kept)


def normalize_mkt(raw: str) -> str:
    """Normalize a single manufacturer_model string to a canonical MKT key.

    Returns an empty string for rows that have no model information.
    """
    if not raw or not raw.strip():
        return ""

    text = _basic_normalize(raw)
    tokens = text.split()

    if not tokens:
        return ""

    # ── Poly family detection ────────────────────────────────────────────────
    # Trigger: "poly" brand present, or "tc\d+" token (TC10 is a Poly-only product).
    # Do NOT trigger on bare x\d+ (would falsely match AMP-X1000, SP-990, etc.).
    has_poly = "poly" in tokens
    has_tc = any(re.match(r"^tc\d+$", t) for t in tokens)

    if has_poly or has_tc:
        if not has_poly and has_tc:
            # TC10 without explicit "poly" brand — it's still a Poly product
            tokens = ["poly"] + tokens
        return _normalize_poly_bundle(tokens)

    # ── General path: remove noise words, join tokens ───────────────────────
    # Step 5: remove noise words
    tokens = [t for t in tokens if t not in NOISE_WORDS]
    return "".join(tokens)


def normalize_file(parsed_file: ParsedFile) -> dict:
    """Add mkt_normalized to every row in the parsed file.

    Returns the file serialized as a plain dict (JSON-compatible) with
    the extra field injected into each row. Does not modify the input.
    """
    data = parsed_file.model_dump()
    for sheet in data["sheets"]:
        for row in sheet["rows"]:
            raw = row["manufacturer_model"] or row["mkt_raw"] or ""
            row["mkt_normalized"] = normalize_mkt(raw)
    return data


# ── Summary printer (run this file directly to verify against real data) ────

def _print_summary(file_a_path: str, file_b_path: str) -> None:
    import json

    seen: dict[str, str] = {}  # original → normalized

    for path in (file_a_path, file_b_path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        contractor = data["meta"]["contractor_id"]
        for sheet in data["sheets"]:
            for row in sheet["rows"]:
                raw = row["manufacturer_model"] or row["mkt_raw"] or ""
                if raw and raw not in seen:
                    seen[raw] = normalize_mkt(raw)

    col = max(len(k) for k in seen) + 2
    print(f"\n{'Original':<{col}} {'Normalized'}")
    print("-" * (col + 40))
    for original, normalized in sorted(seen.items()):
        print(f"{original:<{col}} {normalized}")


if __name__ == "__main__":
    import sys

    base = "data/processed/proj_2026_001"
    _print_summary(
        f"{base}/parsed_contractor_a.json",
        f"{base}/parsed_contractor_b.json",
    )
