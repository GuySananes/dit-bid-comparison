# Data Flow — JSON Schema at Each Pipeline Stage

This document defines exactly what data looks like as it moves through the pipeline.
Every module must consume and produce these schemas precisely.

---

## Stage 0 — Raw Input

Files sitting in `data/raw/`:
- One Excel file per contractor (e.g. `contractor_a.xlsx`, `contractor_b.xlsx`)
- One Excel file for the BOQ / tender spec (e.g. `boq.xlsx`)

No schema — these are unstructured, inconsistent Excel files.

---

## Stage 1 — Parser Output (Layer 1)

Produced by: `src/layer1_parser/excel_reader.py`
Saved to: `data/processed/<project_id>/parsed_<contractor_id>.json`

```json
{
  "meta": {
    "contractor_id": "contractor_a",
    "file_name": "contractor_a.xlsx",
    "project_id": "proj_2026_001",
    "parsed_at": "2026-06-22T10:00:00Z"
  },
  "sheets": [
    {
      "sheet_name": "Meeting room 6P",
      "rows": [
        {
          "row_index": 1,
          "description": "מסך תצוגה ראשי מקצועי LED 65 אינץ 4K UHD 500NIT",
          "unit": "יחידה",
          "quantity": 1,
          "unit_price": 3880,
          "total_price": 3880,
          "manufacturer_model": "SAMSUNG QM65C",
          "mkt_raw": "SAMSUNG QM65C",
          "notes": "",
          "flags": {
            "existing_equipment": false,
            "not_in_total": false,
            "optional": false,
            "math_error": false
          }
        },
        {
          "row_index": 2,
          "description": "מתקן תליה צמוד קיר 65 אינץ",
          "unit": "יחידה",
          "quantity": 1,
          "unit_price": 0,
          "total_price": 0,
          "manufacturer_model": "ציוד קיים",
          "mkt_raw": "",
          "notes": "",
          "flags": {
            "existing_equipment": true,
            "not_in_total": true,
            "optional": false,
            "math_error": false
          }
        }
      ],
      "sheet_total": 26830
    }
  ]
}
```

### Flag rules (applied by the parser script, no AI needed)

| Flag | Trigger condition |
|------|------------------|
| `existing_equipment` | `unit_price` or `total_price` contains "ציוד קיים" / "קיים" |
| `not_in_total` | `total_price` cell contains "לא לסיכום" / "אופציה" |
| `optional` | description or notes contain "אופציה" |
| `math_error` | `quantity × unit_price` differs from `total_price` by more than 1% |

---

## Stage 2A — After Text Normalization

Produced by: `src/layer2_normalization/text_normalizer.py`

Adds a `mkt_normalized` field to each row:

```json
{
  "mkt_raw": "Poly Studio X52 + TC10 + EX MIC",
  "mkt_normalized": "polyx52 tc10 exmic",
  "normalization_steps": ["lowercase", "remove_special_chars", "remove_noise_words"]
}
```

---

## Stage 2B — After Spec Extraction

Produced by: `src/layer2_normalization/spec_extractor.py`

Adds a `specs_extracted` object to each row:

```json
{
  "specs_extracted": {
    "screen_size_inch": 65,
    "brightness_nit": 500,
    "resolution": "4K",
    "response_time_ms": 8,
    "work_hours": "16/7",
    "hdmi_inputs": 2,
    "raw_parse_confidence": 0.91
  }
}
```

---

## Stage 2C — After Embedding Similarity

Produced by: `src/layer2_normalization/embeddings.py`

Each row gets a `mkt_match` object:

```json
{
  "mkt_match": {
    "status": "matched",
    "matched_to": "SAMSUNG QM65C",
    "similarity_score": 0.97,
    "method": "text_normalization",
    "requires_agent": false
  }
}
```

Possible `status` values:
- `matched` — confident match, no agent needed
- `uncertain` — similarity between threshold_low and threshold_high → goes to Agent A
- `no_match` — below threshold_low → flagged for human review
- `existing_equipment` — skip matching

Thresholds defined in `config/settings.py`:
```python
SIMILARITY_THRESHOLD_HIGH = 0.92   # auto-approve
SIMILARITY_THRESHOLD_LOW  = 0.65   # auto-reject, flag for human
```

---

## Stage 3A — After Agent A (Ambiguity Resolution)

Produced by: `src/layer3_agents/agent_a_ambiguity.py`

Updates `mkt_match` for rows where `requires_agent: true`:

```json
{
  "mkt_match": {
    "status": "matched",
    "matched_to": "POLY X52",
    "similarity_score": 0.78,
    "method": "agent_a",
    "agent_reasoning": "Both refer to the Poly Studio X52 codec. 'Studio' is a marketing term added in 2023 rebranding. Same hardware, same SKU base.",
    "agent_confidence": "high",
    "requires_agent": false
  }
}
```

---

## Stage 3B — After Agent B (Technical Deviation)

Produced by: `src/layer3_agents/agent_b_deviation.py`

Adds a `technical_review` object to each row:

```json
{
  "technical_review": {
    "boq_requirement": { "brightness_nit": 500 },
    "contractor_offered": { "brightness_nit": 330 },
    "deviation_detected": true,
    "severity": "major",
    "agent_reasoning": "330 NIT is significantly below the 500 NIT requirement. In a meeting room with standard LED lighting, this will cause visibility issues during daytime use.",
    "rag_sources_used": ["project_2024_a_screen_decision", "NIT_standard_office_guideline"],
    "recommendation": "reject — require replacement with 500 NIT compliant screen"
  }
}
```

Possible `severity` values: `none`, `minor`, `major`, `disqualifying`

---

## Stage 4 — Comparison Table (Script Output)

Produced by: `src/layer3_agents/` comparison script
Saved to: `data/output/<project_id>/comparison_<sheet_name>.xlsx`

Excel file with columns:
```
Row # | Description | Unit | Qty | DIT Notes | 
Contractor A: Unit Price | Total | Model | Contractor Notes | Deviation? |
Contractor B: Unit Price | Total | Model | Contractor Notes | Deviation? |
...
Sheet Total per contractor
```

---

## Stage 5 — Agent C Output (Contractor Reference Sheet)

Produced by: `src/layer3_agents/agent_c_ref_sheet.py`
Saved to: `data/output/<project_id>/ref_sheet_<contractor_id>.pdf`

Plain language document addressed to the contractor listing:
- Items with unrecognized MKTs → must resubmit
- Items with technical deviations → must replace with spec-compliant alternative
- Items with math errors → must correct pricing

---

## Stage 6 — Agent D Output (Executive Summary)

Produced by: `src/layer3_agents/agent_d_summary.py`
Saved to: `data/output/<project_id>/executive_summary.md`

Structured markdown report:
- Total price per contractor per room type
- Cheapest contractor per section
- Completeness score (% of BOQ items filled)
- Top 3 negotiation opportunities
- Recommended next steps
