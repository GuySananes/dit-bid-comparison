# Layer 1 — Excel Parser

## Responsibility

Convert any contractor Excel file into a clean, unified JSON structure.
This layer contains **zero AI** — only deterministic Python logic.

## Files

### `excel_reader.py`

The main parser. Handles the messiness of real-world Excel files:

**What it must solve:**
- Header row is not always row 1 — scan for the row that contains known column names
- Merged cells — `openpyxl` treats merged cells as one value; unmerge and propagate
- Column names vary by contractor — map by content matching, not by position
- Sheet names vary — process all sheets, name them consistently
- Price fields may contain text ("ציוד קיים", "לא לסיכום") instead of numbers — handle gracefully
- Some rows are section headers (bold, no price) — skip them

**Column detection strategy:**
Look for these Hebrew/English keywords to identify columns regardless of position:
```python
DESCRIPTION_KEYWORDS = ["תאור", "תיאור", "description"]
UNIT_KEYWORDS        = ["יחידה", "unit"]
QUANTITY_KEYWORDS    = ["כמות", "qty", "quantity"]
UNIT_PRICE_KEYWORDS  = ["מחיר יחידה", "unit price"]
TOTAL_PRICE_KEYWORDS = ['סה"כ', "total"]
MANUFACTURER_KEYWORDS = ["יצרן", "manufacturer", "model"]
MKT_KEYWORDS         = ['מק"ט', "mkt", "part number", "הערות"]
```

**Flag detection (string matching, no AI):**
```python
def detect_flags(row) -> dict:
    flags = {
        "existing_equipment": False,
        "not_in_total": False,
        "optional": False,
        "math_error": False
    }
    # existing_equipment: price cell contains text instead of number
    # not_in_total: total_price cell contains "לא לסיכום" or "אופציה"
    # math_error: quantity × unit_price ≠ total_price (within tolerance)
    return flags
```

### `schema.py`

Defines the Pydantic models for the JSON output.
Every downstream module imports from here — single source of truth for the data shape.

```python
class ParsedRow(BaseModel):
    row_index: int
    description: str
    unit: str
    quantity: float
    unit_price: float | str   # str when "ציוד קיים"
    total_price: float | str
    manufacturer_model: str
    mkt_raw: str
    notes: str
    flags: RowFlags

class ParsedSheet(BaseModel):
    sheet_name: str
    rows: list[ParsedRow]
    sheet_total: float

class ParsedFile(BaseModel):
    meta: FileMeta
    sheets: list[ParsedSheet]
```

## TODO (implementation order)

- [ ] `schema.py` — define Pydantic models first (all other layers depend on this)
- [ ] `excel_reader.py` — implement header detection
- [ ] `excel_reader.py` — implement merged cell handling
- [ ] `excel_reader.py` — implement column mapping
- [ ] `excel_reader.py` — implement flag detection
- [ ] `excel_reader.py` — implement section header skipping
- [ ] Test on `הצעה 1.xlsx` and `הצעה 2.xlsx`
- [ ] Test on `השוואת מולטימדיה לדוגמא.xlsx` (more complex, multi-contractor)

## Testing

```bash
python -m pytest tests/test_parser.py -v
```

Expected: parser produces valid JSON for all 3 sample Excel files without crashing.
