# Layer 3 — AI Agents

## Responsibility

Handle everything that requires judgment, not just rules.
Every agent receives clean, structured data from Layer 2 — never raw Excel.
Every agent returns structured JSON — never free text that needs parsing.

## Principle

An agent is called only when a script cannot make the decision.
If you find yourself writing an agent for something a regex could do — move it to Layer 2.

---

## `agent_a_ambiguity.py` — Ambiguity Resolution

**Triggered by:** rows where `mkt_match.requires_agent = True`
(similarity score between thresholds — embedding was uncertain)

**Input per call:**
```python
{
    "mkt_a": "POLY X52",                    # from BOQ / approved list
    "mkt_b": "Poly Studio X52 + TC10 MIC",  # from contractor
    "similarity_score": 0.78,
    "context": "..."                         # any RAG context if available
}
```

**Output:**
```python
{
    "is_same_product": True,
    "confidence": "high",
    "reasoning": "Studio is a 2023 rebrand; same hardware.",
    "normalized_name": "Poly X52"
}
```

**Batching:** group all uncertain rows and send in a single prompt if possible
to reduce API calls. Agent A can handle a list of pairs in one call.

**Learning loop:** when Agent A makes a decision with confidence `high` or `medium`,
write the result to Vector DB (`approved_mkts` collection) so the same pair
is resolved automatically next time.

---

## `agent_b_deviation.py` — Technical Deviation

**Triggered by:** every row that has `specs_extracted` data (i.e. the spec extractor found numeric values)

**Input per call:**
```python
{
    "boq_description": "...",
    "boq_specs": {"brightness_nit": 500, "screen_size_inch": 65},
    "contractor_description": "...",
    "contractor_specs": {"brightness_nit": 330, "screen_size_inch": 65},
    "rag_context": "Past decision 2024: 330 NIT rejected for similar office spec..."
}
```

**RAG query before calling agent:**
Before sending to LLM, query Vector DB with:
`"brightness deviation 330 NIT office meeting room"`
Include top 3 results as `rag_context`. This grounds the agent's decision in precedent.

**Output:**
```python
{
    "deviation_detected": True,
    "severity": "major",
    "deviating_fields": ["brightness_nit"],
    "reasoning": "...",
    "recommendation": "request_replacement",
    "rag_sources_used": ["decision_2024_proj_a"]
}
```

**Cost note:** Agent B is called once per row that has specs. Can be expensive.
Consider batching rows from the same sheet in one call (include a list of items).

---

## `agent_c_ref_sheet.py` — Contractor Reference Sheet

**Triggered by:** end of pipeline, once per contractor who has flagged items

**Input:** all flagged rows for that contractor — grouped by issue type:
- `unknown_mkt` — part number not recognized
- `tech_deviation` — spec doesn't meet requirement
- `math_error` — arithmetic inconsistency

**Output:** Hebrew-language formal letter, saved as `.md` (convert to PDF separately).

**Tone:** professional and constructive. Not accusatory.
The contractor needs to understand clearly what to fix and why.

---

## `agent_d_summary.py` — Executive Summary

**Triggered by:** end of pipeline, once per project

**Input:** the full comparison table (totals, scores, deviations) as structured JSON

**Output:** Hebrew-language markdown report with:
- Cost comparison table
- Cheapest per room type
- Negotiation opportunities
- Completeness ranking
- Recommended next steps

---

## `../utils/llm_client.py`

Thin wrapper around the Anthropic SDK. Used by all agents.

```python
def call_llm(system: str, user: str, expect_json: bool = True) -> dict | str:
    """
    Calls Claude with the given system + user prompt.
    If expect_json=True, parses and returns the JSON response.
    Retries once on JSON parse failure.
    Raises LLMError on repeated failure.
    """
```

All agents import from here — no direct `anthropic` SDK calls in agent files.

---

## TODO (implementation order)

- [ ] `../utils/llm_client.py` — build the wrapper first (all agents depend on it)
- [ ] `agent_a_ambiguity.py` — implement with batching
- [ ] `agent_a_ambiguity.py` — add learning loop (write results to Vector DB)
- [ ] `agent_b_deviation.py` — implement RAG query before LLM call
- [ ] `agent_b_deviation.py` — implement batching by sheet
- [ ] `agent_c_ref_sheet.py` — implement
- [ ] `agent_d_summary.py` — implement
- [ ] Test agents on sample data from `הצעה 1.xlsx` + `הצעה 2.xlsx`

## Testing

```bash
python -m pytest tests/test_agents.py -v
```

Use mocked LLM responses in tests — do not call the real API in unit tests.
