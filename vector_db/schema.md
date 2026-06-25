# Vector DB — Schema and Usage

## Purpose

The Vector DB serves as the institutional memory of the system.
It answers the question: "Have we seen this before, and what did we decide?"

Without it, every project starts from zero.
With it, the system gets more accurate with every project that runs through it.

---

## Collections

### 1. `approved_mkts`

Stores known, validated part numbers with their canonical names and aliases.

**Document structure:**
```python
{
    "id": "mkt_poly_x52",
    "text": "Poly X52 polyx52 polycom x52 poly studio x52",  # all known aliases concatenated
    "metadata": {
        "canonical_name": "Poly X52",
        "brand": "Poly",
        "category": "VC system",
        "approved": True,
        "added_from_project": "proj_2024_a",
        "added_at": "2024-03-15"
    }
}
```

**How it grows:**
- Manually seeded from known product lists
- Agent A adds new confirmed matches with `confidence: high`
- Project managers can add entries via a simple CLI command

**Query:** `"polyx52"` → returns nearest matches with similarity scores

---

### 2. `past_decisions`

Stores Agent B's technical deviation rulings from past projects.
Used as RAG context when Agent B evaluates similar deviations in new projects.

**Document structure:**
```python
{
    "id": "decision_2024_proj_a_brightness",
    "text": "330 NIT screen offered instead of 500 NIT requirement. Meeting room office use. Rejected — major deviation.",
    "metadata": {
        "project_id": "proj_2024_a",
        "deviation_type": "brightness_nit",
        "boq_value": 500,
        "offered_value": 330,
        "severity": "major",
        "decision": "reject",
        "reasoning": "...",
        "decided_at": "2024-03-20"
    }
}
```

**How it grows:**
- Agent B writes its decisions here automatically after each project
- Project managers can override/annotate decisions via CLI

**Query:** `"brightness NIT deviation office meeting room"` → returns similar past rulings

---

### 3. `product_specs`

Stores manufacturer datasheet content — used when Agent B needs to verify
what a product actually offers vs what the contractor claims.

**Document structure:**
```python
{
    "id": "spec_samsung_qm65c",
    "text": "Samsung QM65C professional display. 500 NIT brightness. 4K UHD 3840x2160. 16/7 operation. G-to-G response 8ms. RS-232/485 control. HDMI x2 HDCP 2.2.",
    "metadata": {
        "product_name": "Samsung QM65C",
        "brand": "Samsung",
        "category": "professional display",
        "source": "samsung_datasheet_2023.pdf",
        "added_at": "2024-01-01"
    }
}
```

**How it grows:**
- Manually populated from manufacturer PDFs
- Future: automated ingestion pipeline for datasheets

**Query:** `"SAMSUNG QM65C brightness NIT"` → returns spec sheet text

---

## `store.py` — Interface

```python
class VectorStore:

    def add_mkt(self, canonical_name: str, aliases: list[str], metadata: dict) -> None:
        """Add a new approved part number with all its known aliases."""

    def query_mkt(self, mkt_string: str, top_k: int = 5) -> list[SearchResult]:
        """Find the closest known part numbers to a given string."""

    def add_decision(self, decision: dict) -> None:
        """Store a technical deviation ruling for future RAG use."""

    def query_decisions(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """Retrieve past rulings relevant to a given deviation query."""

    def add_product_spec(self, product_name: str, spec_text: str, metadata: dict) -> None:
        """Add manufacturer spec content."""

    def query_product_specs(self, query: str, top_k: int = 2) -> list[SearchResult]:
        """Retrieve relevant spec content for a product."""
```

---

## Seeding the DB for the first project

Before running the pipeline on a real project, populate the DB with known data:

```bash
python vector_db/seed.py --mkts data/seed/known_mkts.csv
python vector_db/seed.py --specs data/seed/product_specs/
```

`known_mkts.csv` format:
```
canonical_name,aliases,brand,category
Poly X52,"POLY X52,polycom x52,poly studio x52",Poly,VC system
Samsung QM65C,"SAMSUNG QM65C,samsung qm65c-n,QM65C",Samsung,Professional display
```

---

## Privacy note

The Vector DB stores **product names and technical decisions only** — not contractor prices.
Contractor pricing data stays in the processed JSON files and never enters the Vector DB.
This means the DB can be shared across projects and clients without leaking commercial information.
