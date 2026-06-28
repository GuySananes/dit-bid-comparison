# CLAUDE.md

This file is read automatically by Claude Code at the start of every session.
Do not delete or rename it.

---

## Project: DIT Bid Comparison Pipeline

An AI-powered agent pipeline that automates the comparison of contractor bids
for professional AV / multimedia installations.

**Context:** After a tender is issued, multiple contractors submit Excel price proposals
in inconsistent formats. A project manager currently compares them manually, line by line.
This system replaces that manual process.

---

## Core Principle — Read This First

> Use a **script** for anything that can be defined as a rule.
> Use **embeddings** for similarity matching.
> Use an **AI agent** only when judgment is required.
> Use **RAG** for historical institutional knowledge.

If you find yourself writing an LLM call for something a regex or a dict lookup
could handle — stop and move it to Layer 2 instead.

---

## Architecture — Three Layers

```
Layer 1 — Raw Processing   (Python scripts, zero AI)
Layer 2 — Normalization    (scripts + local embeddings, zero LLM calls)
Layer 3 — AI Agents        (LLM only for judgment and natural language output)
                    ↕
            Vector DB (RAG) — institutional memory across projects
```

Full architecture: see `README.md`
Data shapes at each stage: see `docs/data_flow.md`
Why we made each design decision: see `docs/decisions.md`
Domain knowledge (what is a מכרז, BOQ, מק"ט): see `docs/onboarding.md`

---

## Folder Structure

```
dit-bid-comparison/
├── CLAUDE.md                        ← you are here
├── IMPLEMENTATION_ORDER.md          ← build order, step by step
├── README.md                        ← project overview
├── main.py                          ← pipeline orchestrator (build last)
├── requirements.txt
├── config/
│   ├── settings.py                  ← API keys, thresholds (never commit)
│   └── prompts.py                   ← all LLM prompts, versioned
├── data/
│   ├── raw/                         ← input Excel files (never commit)
│   ├── processed/                   ← intermediate JSON (never commit)
│   └── output/                      ← final reports (never commit)
├── docs/
│   ├── data_flow.md                 ← JSON schema at every pipeline stage
│   ├── onboarding.md                ← domain knowledge
│   └── decisions.md                 ← architectural decision log
├── src/
│   ├── layer1_parser/
│   │   ├── schema.py                ← Pydantic models — single source of truth ✓ DONE
│   │   └── excel_reader.py          ← flexible Excel ingestion
│   ├── layer2_normalization/
│   │   ├── text_normalizer.py       ← MKT string normalization
│   │   ├── spec_extractor.py        ← extract NIT, inch, MS from descriptions
│   │   ├── math_validator.py        ← qty × price = total check
│   │   └── embeddings.py            ← vector similarity matching
│   ├── layer3_agents/
│   │   ├── agent_a_ambiguity.py     ← resolve uncertain MKT matches
│   │   ├── agent_b_deviation.py     ← judge technical deviations
│   │   ├── agent_c_ref_sheet.py     ← generate contractor feedback letter
│   │   └── agent_d_summary.py       ← generate executive summary
│   └── utils/
│       ├── llm_client.py            ← Anthropic API wrapper
│       └── logger.py                ← structured logging
├── tests/
│   ├── test_parser.py
│   ├── test_normalizer.py
│   └── test_agents.py               ← uses mocked LLM, never calls real API
└── vector_db/
    ├── schema.md                    ← what gets stored and why
    └── store.py                     ← VectorStore class
```

---

## Environment

- **Python:** use `py` not `python` (Windows, PATH issue)
- **Virtual env:** always active at `venv\Scripts\activate` before running anything
- **Package manager:** pip, packages defined in `requirements.txt`
- **LLM:** Anthropic Claude via `anthropic` SDK — model defined in `config/settings.py`
- **Embeddings:** `sentence-transformers`, model `all-MiniLM-L6-v2`, runs locally
- **Vector DB:** ChromaDB, stored at `vector_db/chroma/` (local, never committed)

---

## Key Rules — Always Follow These

1. **Never modify `src/layer1_parser/schema.py` without explicit instruction.**
   All layers depend on it. A change there breaks everything downstream.

2. **Never put LLM calls in Layer 1 or Layer 2.**
   If you think you need one there, ask first.

3. **Never commit these paths** (already in `.gitignore` — verify before any `git add`):
   - `config/settings.py` (contains API key)
   - `data/raw/` (contractor pricing data)
   - `data/processed/` and `data/output/`
   - `vector_db/chroma/`

4. **All agent prompts live in `config/prompts.py`** — not inline in agent files.
   This makes them easy to version and improve independently.

5. **Agents always return structured JSON** — never free text that needs parsing downstream.
   If an agent returns prose, it's a bug.

6. **Tests never call the real Anthropic API.**
   Use mocked responses in `tests/test_agents.py`.

7. **Read the relevant README before writing any module.**
   Each layer folder has a README with exact requirements and test cases.

---

## Build Order

See `IMPLEMENTATION_ORDER.md` for the full step-by-step guide with prompts.

Current status:
- [x] Step 1 — `schema.py` ✓
- [x] Step 2 — `excel_reader.py` ✓
- [x] Step 3 — `text_normalizer.py` ✓
- [x] Step 4 — `spec_extractor.py` ✓
- [x] Step 5 — `math_validator.py` ✓
- [x] Step 6 — `llm_client.py` ✓
- [x] Step 7 — `store.py` (Vector DB) ✓
- [x] Step 8 — `embeddings.py` ✓
- [ ] Step 9 — `agent_a_ambiguity.py`
- [ ] Step 10 — `agent_b_deviation.py`
- [ ] Step 11 — `build_comparison_table.py`
- [ ] Step 12 — `agent_c_ref_sheet.py`
- [ ] Step 13 — `agent_d_summary.py`
- [ ] Step 14 — `main.py`
- [ ] Step 15 — tests

---

## Useful Commands

```powershell
# activate venv (always first)
venv\Scripts\activate

# run tests
py -m pytest tests/ -v

# run a single test file
py -m pytest tests/test_parser.py -v

# run the pipeline (after main.py is built)
py main.py --input data/raw/ --boq data/raw/boq.xlsx --project "test_run_01"

# check what's installed
pip list
```

---

## Sample Data

Three real Excel files are available in `data/raw/` for testing:
- `הצעה 1.xlsx` — contractor A full proposal (multiple room types)
- `הצעה 2.xlsx` — contractor B full proposal (multiple room types)
- `השוואת מולטימדיה לדוגמא.xlsx` — example of the target output format (4 contractors side by side)

The target output format is the comparison Excel — study it before building
`build_comparison_table.py`.
