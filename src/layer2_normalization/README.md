# Layer 2 — Normalization

## Responsibility

Transform the parsed JSON into comparable, structured data.
Resolve part number identity wherever possible **without AI**.
Only rows that cannot be resolved here are escalated to Layer 3 agents.

## Files

---

### `text_normalizer.py`

Normalizes raw MKT strings so that variations of the same part number become identical strings.

**Input field — data-specific decision:**
Normalization runs on `manufacturer_model`, not `mkt_raw`.
In this dataset (`proj_2026_001`), `mkt_raw` is empty for the vast majority of rows;
contractors filled in `manufacturer_model` instead.
If a future dataset reverses this pattern, the fallback in `normalize_file()` already
tries `mkt_raw` when `manufacturer_model` is empty, so no logic change is needed —
only the priority order would need to flip.

**Steps applied in order:**
1. Lowercase everything
2. Strip leading/trailing whitespace
3. Remove special characters: `-`, `/`, `+`, `.`, `"`, `'`
4. Collapse multiple spaces to single space
5. Remove known noise words: `studio`, `professional`, `series`, `kit`, `bundle`, `black`
6. Normalize brand aliases: `polycom` → `poly`, `samsung qm` → `samsungqm`
7. Strip bundle suffixes: `+ tc10 + mic` → keep only the core model identifier

**Example:**
```
"Poly Studio X52 + TC10 + EX MIC"  →  "polyx52"
"POLY X52"                          →  "polyx52"   ← match!
"polycom studio x52 bundle"         →  "polyx52"   ← match!
```

**Output:** adds `mkt_normalized` to each row.

---

### `spec_extractor.py`

Extracts numeric technical values from free-text descriptions using regex patterns.

**Patterns to extract:**

| Field | Pattern examples | Output field |
|-------|-----------------|--------------|
| Screen size | `65 אינץ`, `65"`, `65 inch` | `screen_size_inch` |
| Brightness | `500NIT`, `500 NIT`, `350 nit` | `brightness_nit` |
| Resolution | `4K`, `4K UHD`, `3840*2160`, `FHD` | `resolution` |
| Response time | `8MS`, `8 ms`, `G TO G 8MS` | `response_time_ms` |
| Work hours | `16/7`, `24/7` | `work_hours` |
| HDMI inputs | `2 כניסות HDMI`, `HDMI x2` | `hdmi_inputs` |
| Camera zoom | `PTZ zoomX12`, `12X zoom` | `camera_zoom_x` |

**Output:** adds `specs_extracted` dict to each row, plus `raw_parse_confidence` (0–1).

**Important:** this module only extracts — it does NOT compare against the BOQ.
Comparison happens in Agent B.

---

### `math_validator.py`

Validates arithmetic consistency across every row.

**Check:**
```
abs(quantity × unit_price - total_price) / total_price > MATH_ERROR_TOLERANCE
```

**Edge cases:**
- Skip rows where `existing_equipment = True` (no price to validate)
- Skip rows where `unit_price` or `total_price` is a string, not a number
- Skip rows where `quantity = 0`

**Output:** sets `flags.math_error = True` on failing rows, adds `math_error_detail` string.

---

### `embeddings.py`

For rows where text normalization produced no exact match, compute vector similarity
between `mkt_normalized` strings.

**Flow:**
1. Load embedding model (local, `sentence-transformers`)
2. For each unmatched row, embed its `mkt_normalized`
3. Query Vector DB for nearest neighbors in `approved_mkts` collection
4. If top result > `SIMILARITY_THRESHOLD_HIGH` → auto-match
5. If top result between thresholds → flag `requires_agent = True` → goes to Agent A
6. If top result < `SIMILARITY_THRESHOLD_LOW` → flag `no_match`, human review

**Why local embeddings (not API)?**
- Speed: no network call per row
- Cost: free
- Privacy: contractor pricing data never leaves the machine
- `all-MiniLM-L6-v2` is strong enough for product name similarity

**Output:** adds `mkt_match` object to each row (see `docs/data_flow.md` for schema).

---

## TODO (implementation order)

- [ ] `text_normalizer.py` — implement normalization pipeline
- [ ] `text_normalizer.py` — build noise word list from sample data
- [ ] `spec_extractor.py` — implement regex patterns for all fields
- [ ] `spec_extractor.py` — compute `raw_parse_confidence` based on how many fields extracted
- [ ] `math_validator.py` — implement with edge case handling
- [ ] `embeddings.py` — load model + basic similarity
- [ ] `embeddings.py` — integrate with Vector DB query
- [ ] Run full normalization on both `הצעה 1.xlsx` and `הצעה 2.xlsx`
- [ ] Measure: what % of MKTs resolve at text normalization vs need embeddings vs need agent?

## Testing

```bash
python -m pytest tests/test_normalizer.py -v
```

Key test cases:
- `"POLY X52"` and `"Poly Studio X52"` → same after normalization
- `"SAMSUNG QB65C-N"` and `"samsung qb65cn"` → same
- `"Msolutions MS-070"` and `"M Solutions MS070"` → same
- `"POLY X52"` and `"POLY X72"` → different (model number matters)
- Row with `unit_price=4500, quantity=3, total_price=13000` → `math_error=True`
