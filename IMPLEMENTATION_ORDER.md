# IMPLEMENTATION_ORDER.md

A step-by-step guide for building the DIT Bid Comparison pipeline.
Follow this order exactly — each step depends on the previous one.

---

## Before You Start

1. Download and unzip `dit-bid-comparison.zip` to your local machine
2. Open the folder in your terminal
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate        # Mac/Linux
   venv\Scripts\activate           # Windows
   pip install -r requirements.txt
   ```
4. Copy `config/settings.py` and add your `ANTHROPIC_API_KEY`
5. Open the folder with Claude Code:
   ```bash
   claude
   ```

---

## Step 1 — Data Schema (`src/layer1_parser/schema.py`)

**Build first. Everything else imports from here.**

Ask Claude Code:
> "Create `src/layer1_parser/schema.py`. Define Pydantic models for the pipeline's
> data structures based on the JSON schema in `docs/data_flow.md`.
> Models needed: `RowFlags`, `ParsedRow`, `ParsedSheet`, `FileMeta`, `ParsedFile`."

Done when: `from src.layer1_parser.schema import ParsedFile` works without error.

---

## Step 2 — Excel Parser (`src/layer1_parser/excel_reader.py`)

**Converts any contractor Excel into unified JSON.**

Ask Claude Code:
> "Create `src/layer1_parser/excel_reader.py`. Read the README at
> `src/layer1_parser/README.md` for full requirements.
> The parser must handle: flexible header row detection, merged cells,
> column mapping by keyword, flag detection (existing equipment, math errors).
> Input: path to an Excel file. Output: a `ParsedFile` object serialized to JSON."

Test immediately:
> "Run the parser on `data/raw/הצעה 1.xlsx` and print the JSON output.
> Fix any errors until it produces valid output."

Done when: both `הצעה 1.xlsx` and `הצעה 2.xlsx` parse without errors.

---

## Step 3 — Text Normalizer (`src/layer2_normalization/text_normalizer.py`)

**Resolves most MKT variations without any AI.**

Ask Claude Code:
> "Create `src/layer2_normalization/text_normalizer.py`.
> Read `src/layer2_normalization/README.md` for the normalization steps.
> Input: a `ParsedFile`. Output: same structure with `mkt_normalized` added to each row.
> Test that 'Poly Studio X52 + TC10 + EX MIC' and 'POLY X52' normalize to the same string."

Done when: the key test cases in the Layer 2 README all pass.

---

## Step 4 — Spec Extractor (`src/layer2_normalization/spec_extractor.py`)

**Extracts numbers from free text so specs can be compared.**

Ask Claude Code:
> "Create `src/layer2_normalization/spec_extractor.py`.
> Read `src/layer2_normalization/README.md` for the regex patterns needed.
> Input: a row's description string. Output: a `specs_extracted` dict with fields
> like `screen_size_inch`, `brightness_nit`, `resolution`, `response_time_ms`.
> Test on real description strings from `הצעה 1.xlsx`."

Done when: `brightness_nit: 330` is correctly extracted from `"עוצמת הארה 330NIT"`.

---

## Step 5 — Math Validator (`src/layer2_normalization/math_validator.py`)

**Catches arithmetic errors in contractor proposals.**

Ask Claude Code:
> "Create `src/layer2_normalization/math_validator.py`.
> Input: a `ParsedFile`. For each row, check that quantity × unit_price = total_price
> within 1% tolerance. Set `flags.math_error = True` on failing rows.
> Skip rows where existing_equipment or not_in_total flags are set.
> Add a `math_error_detail` string explaining the discrepancy."

Done when: a row with `quantity=3, unit_price=4500, total_price=13000` is flagged.

---

## Step 6 — LLM Client Wrapper (`src/utils/llm_client.py`)

**Write once, used by all four agents.**

Ask Claude Code:
> "Create `src/utils/llm_client.py`.
> Implement a `call_llm(system, user, expect_json=True)` function that:
> - Calls the Anthropic API using settings from `config/settings.py`
> - If `expect_json=True`, parses the response as JSON and retries once on failure
> - Raises a clear `LLMError` with the raw response if JSON parsing fails twice
> - Logs every call (model, token count, duration) using the standard `logging` module"

Done when: a test call returns a parsed dict successfully.

---

## Step 7 — Vector DB Store (`vector_db/store.py`)

**The institutional memory. Needed before agents can use RAG.**

Ask Claude Code:
> "Create `vector_db/store.py`.
> Implement the `VectorStore` class defined in `vector_db/schema.md`.
> Use ChromaDB as the backend (path from `config/settings.py`).
> Implement: `add_mkt`, `query_mkt`, `add_decision`, `query_decisions`,
> `add_product_spec`, `query_product_specs`.
> Use `sentence-transformers` (model from settings) for embeddings."

Then seed with known data:
> "Create `vector_db/seed.py` that reads a CSV of known MKTs and loads them
> into the Vector DB using `VectorStore.add_mkt`."

Done when: querying `"polyx52"` returns `"Poly X52"` as the top result.

---

## Step 8 — Embeddings Matcher (`src/layer2_normalization/embeddings.py`)

**Handles MKTs that text normalization couldn't resolve.**

Ask Claude Code:
> "Create `src/layer2_normalization/embeddings.py`.
> Input: a `ParsedFile` after text normalization.
> For each row where `mkt_normalized` didn't find an exact match:
>   - Query `VectorStore.query_mkt` with the normalized string
>   - If top score > SIMILARITY_THRESHOLD_HIGH: auto-match, set `mkt_match.status = matched`
>   - If between thresholds: set `mkt_match.requires_agent = True`
>   - If below SIMILARITY_THRESHOLD_LOW: set `mkt_match.status = no_match`
> Read `docs/data_flow.md` Stage 2C for the exact output schema."

Done when: unrecognized MKTs are correctly bucketed into matched / uncertain / no_match.

---

## Step 9 — Agent A: Ambiguity (`src/layer3_agents/agent_a_ambiguity.py`)

**Resolves uncertain MKT matches using the LLM.**

Ask Claude Code:
> "Create `src/layer3_agents/agent_a_ambiguity.py`.
> Collect all rows where `mkt_match.requires_agent = True`.
> Use the prompt from `config/prompts.py` (AGENT_A_SYSTEM + AGENT_A_USER).
> Batch multiple uncertain pairs into a single LLM call where possible.
> After each decision with confidence 'high' or 'medium', write the result
> to VectorStore so it resolves automatically next time.
> Read `src/layer3_agents/README.md` for the full spec."

Done when: `"Poly Studio X52"` vs `"POLY X52"` resolves to `is_same_product: true`.

---

## Step 10 — Agent B: Technical Deviation (`src/layer3_agents/agent_b_deviation.py`)

**Judges whether a contractor's offer meets the spec.**

Ask Claude Code:
> "Create `src/layer3_agents/agent_b_deviation.py`.
> For each row that has `specs_extracted` data:
>   1. Query VectorStore for past decisions on similar deviations (RAG)
>   2. Call LLM with AGENT_B_SYSTEM + AGENT_B_USER from `config/prompts.py`
>      including the RAG context
>   3. Store the decision back in VectorStore for future projects
> Read `docs/data_flow.md` Stage 3B for the exact output schema."

Done when: a 330 NIT offer against a 500 NIT requirement returns `severity: major`.

---

## Step 11 — Comparison Table Script

**Builds the final Excel comparison file — no AI, just data assembly.**

Ask Claude Code:
> "Create `src/layer3_agents/build_comparison_table.py`.
> Input: all parsed + normalized + agent-reviewed contractor files for a project.
> Output: an Excel file (using xlsxwriter) where:
>   - Each sheet = one room type
>   - Rows = BOQ line items
>   - Columns = one set per contractor (unit price, total, model, deviation flag)
>   - Red cell background on rows with major/disqualifying deviations
>   - Bold totals row per contractor per sheet
> Format should match the structure in `השוואת מולטימדיה לדוגמא.xlsx`."

Done when: the output Excel visually matches the example comparison file.

---

## Step 12 — Agent C: Contractor Reference Sheet (`src/layer3_agents/agent_c_ref_sheet.py`)

Ask Claude Code:
> "Create `src/layer3_agents/agent_c_ref_sheet.py`.
> Collect all flagged rows for a given contractor (unknown MKT, tech deviation, math error).
> Use AGENT_C_SYSTEM + AGENT_C_USER from `config/prompts.py`.
> Output: a Hebrew-language markdown file saved to `data/output/<project_id>/ref_sheet_<contractor_id>.md`."

---

## Step 13 — Agent D: Executive Summary (`src/layer3_agents/agent_d_summary.py`)

Ask Claude Code:
> "Create `src/layer3_agents/agent_d_summary.py`.
> Input: the full comparison table data as structured JSON.
> Use AGENT_D_SYSTEM + AGENT_D_USER from `config/prompts.py`.
> Output: a Hebrew-language markdown file saved to `data/output/<project_id>/executive_summary.md`."

---

## Step 14 — Pipeline Orchestrator (`main.py`)

**Wire everything together. Do this last.**

Ask Claude Code:
> "Implement `main.py`. It should run the full pipeline in order:
> Layer 1 → Layer 2 (all three normalizers + embeddings) → Agent A → Agent B
> → Comparison Table → Agent C → Agent D → Vector DB learning loop.
> Save intermediate JSON to `data/processed/<project_id>/` after each layer
> so the pipeline can resume from any step.
> Log the start and end of each step with timing."

Test the full pipeline:
> "Run `python main.py --input data/raw/ --boq data/raw/boq.xlsx --project test_run_01`
> and fix any integration errors."

---

## Step 15 — Tests

Ask Claude Code:
> "Write `tests/test_parser.py` covering: header detection, merged cells,
> flag detection, math error detection. Use the sample Excel files as fixtures."

> "Write `tests/test_normalizer.py` covering the key test cases in
> `src/layer2_normalization/README.md`."

> "Write `tests/test_agents.py` with mocked LLM responses so tests run
> without hitting the real API."

---

## Quick Reference — What Each File Does

| File | What it does | AI? |
|------|-------------|-----|
| `schema.py` | Defines data shapes | No |
| `excel_reader.py` | Reads any Excel format | No |
| `text_normalizer.py` | Cleans MKT strings | No |
| `spec_extractor.py` | Pulls numbers from descriptions | No |
| `math_validator.py` | Checks qty × price = total | No |
| `llm_client.py` | Anthropic API wrapper | — |
| `store.py` | Vector DB read/write | No |
| `embeddings.py` | Similarity matching | No (local model) |
| `agent_a_ambiguity.py` | Resolves uncertain MKTs | **Yes** |
| `agent_b_deviation.py` | Judges tech deviations | **Yes** |
| `build_comparison_table.py` | Builds Excel output | No |
| `agent_c_ref_sheet.py` | Writes contractor letter | **Yes** |
| `agent_d_summary.py` | Writes executive summary | **Yes** |
| `main.py` | Runs the full pipeline | — |
