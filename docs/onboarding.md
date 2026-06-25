# docs/onboarding.md
# Domain Knowledge — AV Procurement in Israel

This document explains the business domain so that code decisions
are grounded in real-world context, not just technical assumptions.
Read this before working on any agent or normalization logic.

---

## The Business Process — End to End

### 1. A project starts with a tender (מכרז)

A company (the client) decides to install AV/multimedia systems in their offices —
meeting rooms, boardrooms, private offices. They hire a consulting firm like DIT
to manage the process.

DIT writes a **BOQ (Bill of Quantities)** — a detailed specification document
listing every item needed, with technical requirements but no prices.
Example line from a BOQ:

> "Professional LED display, 65 inch, 4K UHD, 500 NIT brightness,
>  16/7 operation, RS-232 control, 2x HDMI inputs, 3-year warranty — 1 unit"

### 2. Contractors submit proposals (הצעות)

Multiple AV contractors (קבלנים) receive the BOQ and submit Excel files
with their pricing. Each contractor fills in:
- Which product they are offering (manufacturer + model)
- Their price per unit
- Their total price (quantity × unit price)
- A part number / catalog number (מק"ט)

**Key problem:** Every contractor builds their Excel differently.
Different column order, different Hebrew spelling, merged cells, colored rows.
There is no standard format.

### 3. DIT builds a comparison table (טבלת השוואה)

A project manager manually copies prices from all contractor Excels into one
master comparison table — contractors side by side, same BOQ line items in rows.

This is what this pipeline automates.

### 4. Technical and commercial comparison

Two separate evaluations happen:

**Technical:** Did the contractor offer what was asked?
- Correct screen size? Correct brightness? Correct resolution?
- If not → flagged as a deviation (חריגה)

**Commercial:** Who is cheapest for each item?
- Must compare "apples to apples" — only after technical compliance is confirmed

### 5. Contractor reference sheet (דף התייחסות)

Contractors whose proposals have problems receive a formal letter listing:
- Unrecognized part numbers → must resubmit with valid MKT
- Technical deviations → must replace with compliant product
- Arithmetic errors → must correct pricing

### 6. Award

After corrections, DIT recommends a contractor (or split award by room type)
to the client.

---

## Key Terms

### מק"ט (MKT) — Part Number / Catalog Number

A unique identifier for a specific product from a specific manufacturer.
Think of it like a SKU.

Examples:
- `SAMSUNG QB65C-N` — Samsung 65" professional display, model QB65C-N
- `POLY X52` — Poly (formerly Polycom) video conferencing system X52
- `Msolutions MS-070` — HDMI extender by M Solutions

**Why MKTs are hard:**
- Contractors write them inconsistently: `QB65C-N`, `QB65CN`, `QB65C N`, `samsung qb65`
- Manufacturers rebrand: Polycom → Poly (same products, new name)
- Bundles: `POLY X52 + TC10 + EX MIC` is a bundle — core product is `POLY X52`
- Sometimes contractors invent their own codes

### BOQ (Bill of Quantities) — כמויות מכרז

The official tender document listing what is needed.
This is the "question". Contractor proposals are the "answers".
Every BOQ line has a line number (מספר סעיף) that must match across all proposals.

### ציוד קיים — Existing Equipment

The client already owns this item. The contractor does not need to supply it.
Price = 0 or the cell contains the text "ציוד קיים".
Must be excluded from totals and from technical comparison.

### לא לסיכום — Not in Total

Item is shown for reference or as an option but NOT included in the contract total.
Examples: optional accessories, sensors, wireless presentation systems.
Must be excluded from price totals.

### אופציה — Option

Similar to "לא לסיכום" — contractor prices it but it is not part of the base scope.

### NIT — Brightness Unit

Nits (candela per square meter) — measures screen brightness.
Higher = better visibility in bright environments.
Typical office requirement: 350–500 NIT.
A contractor offering 330 NIT when 500 NIT is required = major deviation.

### VC System — Video Conferencing

The camera + codec + microphone system for video calls (Zoom, Teams).
Common brands: Poly, Logitech, Cisco, Crestron.
Sized by room capacity: 6P (6 people), 10P, 20P, board room.

### PTZ Camera

Pan-Tilt-Zoom camera for large meeting rooms.
Common spec: zoom X12 (12x optical zoom).

### HDMI Extender (הרחקת HDMI)

Device that sends HDMI signal over Cat5/Cat6 cable across long distances.
Consists of a transmitter + receiver pair.
Common: `Msolutions MS-070`, `Kramer` products.

### Crestron / Extron

Leading brands for AV control systems, matrix switchers, and connection boxes.
Expensive but widely specified. Many MKTs start with these brand names.

---

## Room Types in This Project

The sample data covers these room types (each is a separate sheet in Excel):

| Room Type | Hebrew | Typical Size | Key Equipment |
|-----------|--------|-------------|---------------|
| Meeting room 6P | חדר ישיבות 6 משתתפים | Small | 65" screen, VC system |
| Meeting room 20P | חדר ישיבות 20 משתתפים | Large | 86" screen, VC system, audio |
| Board room | חדר בורד | Very large | 110" screen, PTZ cameras, full audio |
| Senior office | משרד בכיר | Single person | 65" screen, no VC |

---

## Common Technical Deviations to Watch For

| Spec | BOQ typical requirement | Common contractor deviation |
|------|------------------------|----------------------------|
| Brightness | 500 NIT | 330–350 NIT offered |
| Screen type | Professional display (מקצועי) | Consumer/Smart TV offered |
| Operation hours | 16/7 | Consumer screen (not rated for 16/7) |
| Warranty | 3 years | 1 year offered |
| Resolution | 4K UHD | FHD (1080p) offered |
| Camera | PTZ zoom X12 | Fixed camera offered |

---

## What "Apples to Apples" Means

Before comparing prices, every line item must be technically equivalent.

Example — two contractors offer a 65" screen:
- Contractor A: `SAMSUNG QM65C` — professional, 500 NIT, 16/7 — ₪3,880
- Contractor B: `LG 65UM5N` — professional, 330 NIT, 16/7 — ₪3,750

Contractor B is cheaper but does NOT meet the 500 NIT requirement.
Comparing their prices directly is misleading — they are not the same product.

The pipeline must flag Contractor B's deviation BEFORE any price comparison.

---

## Data Privacy Notes

Contractor pricing is commercially sensitive.
- Never store prices in the Vector DB
- Never log prices to console output
- `data/raw/` and `data/output/` are in `.gitignore` for this reason
- The Vector DB stores only product names and technical decisions
