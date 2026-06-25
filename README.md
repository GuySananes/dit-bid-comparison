# DIT Bid Comparison System

An AI-powered agent pipeline that automates the process of comparing multimedia AV contractor bids.

## Problem

After a tender (מכרז) is issued, multiple contractors submit Excel price proposals in inconsistent formats. A project manager currently compares them manually, line by line, relying on personal knowledge to validate part numbers (מק"טים) and flag technical deviations. This process is slow, error-prone, and non-scalable.

## Solution

A three-layer pipeline:

1. **Layer 1 — Raw Processing** (Python scripts): Parse any Excel format into a unified JSON structure
2. **Layer 2 — Normalization** (scripts + embeddings): Text normalization, spec extraction, math validation, embedding similarity
3. **Layer 3 — AI Agents** (LLM): Ambiguity resolution, technical deviation judgment, output generation

Plus a **Vector DB** (RAG) that accumulates institutional knowledge across projects.

## Architecture

```
Excel files (contractors + BOQ)
        │
        ▼
[ Layer 1: Python Parser ]
        │
        ▼
[ Unified JSON ]
        │
   ┌────┴─────────────────┐
   ▼                      ▼                    ▼
[ Text Normalization ] [ Spec Extraction ] [ Math Validation ]
        │
        ▼
[ Embeddings Similarity ]
        │
   ┌────┴────┐
   ▼         ▼
[ Agent A ] [ Agent B ] ←──→ [ Vector DB / RAG ]
 Ambiguity   Tech Deviation
        │
        ▼
[ Comparison Table Script ]
        │
   ┌────┴────┐
   ▼         ▼
[ Agent C ] [ Agent D ]
 Contractor  Executive
 Ref Sheet   Summary
        │
        ▼
[ Outputs: Excel + PDF reports ]
        │
        └──────────────────→ [ Vector DB ] (learning loop)
```

## Folder Structure

```
dit-bid-comparison/
├── README.md
├── config/
│   ├── settings.py          # API keys, model names, thresholds
│   └── prompts.py           # All LLM prompts (versioned)
├── data/
│   ├── raw/                 # Input Excel files from contractors
│   ├── processed/           # Intermediate JSON files
│   └── output/              # Final comparison tables and reports
├── src/
│   ├── layer1_parser/
│   │   ├── excel_reader.py  # Flexible Excel ingestion
│   │   └── schema.py        # JSON output schema definition
│   ├── layer2_normalization/
│   │   ├── text_normalizer.py   # MKT string normalization
│   │   ├── spec_extractor.py    # Extract NIT, inch, MS values
│   │   ├── math_validator.py    # qty × price = total check
│   │   └── embeddings.py        # Vector similarity matching
│   ├── layer3_agents/
│   │   ├── agent_a_ambiguity.py     # Resolve unmatched MKTs
│   │   ├── agent_b_deviation.py     # Judge technical deviations
│   │   ├── agent_c_ref_sheet.py     # Generate contractor feedback
│   │   └── agent_d_summary.py       # Generate executive summary
│   └── utils/
│       ├── llm_client.py    # Wrapper for Anthropic API calls
│       └── logger.py        # Structured logging
├── vector_db/
│   ├── store.py             # Vector DB read/write interface
│   └── schema.md            # What gets stored and why
├── tests/
│   ├── test_parser.py
│   ├── test_normalizer.py
│   └── test_agents.py
├── docs/
│   └── data_flow.md         # JSON schema at each pipeline stage
└── main.py                  # Pipeline orchestrator — runs everything
```

## Guiding Principle

> Use a script for anything that can be defined as a rule.
> Use embeddings for similarity.
> Use an AI agent only for judgment.
> Use RAG for historical institutional knowledge.

## Stack

- Python 3.11+
- `openpyxl` — Excel parsing
- `anthropic` — LLM API (Claude)
- `sentence-transformers` — local embeddings
- `chromadb` — local Vector DB (can swap to Pinecone)
- `openpyxl` / `xlsxwriter` — Excel output

## Setup

```bash
git clone <repo>
cd dit-bid-comparison
pip install -r requirements.txt
cp config/settings.example.py config/settings.py
# add your ANTHROPIC_API_KEY to settings.py
python main.py --input data/raw/ --project "Project Name"
```
