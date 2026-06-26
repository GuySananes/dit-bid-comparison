"""Layer 2 — Arithmetic consistency validator.

For each row, checks that quantity × unit_price ≈ total_price within tolerance.
Flags discrepancies without modifying any other field.

Skip conditions (row is left untouched):
  - existing_equipment is True  (price field is a label, e.g. "ציוד קיים")
  - not_in_total is True        (row intentionally excluded from sum)
  - unit_price is not a number  (string value such as "ציוד קיים")
  - total_price is not a number (string value or empty string)
  - quantity == 0               (nothing to validate; avoids division quirks)

Output (mutates the serialised row dict in-place):
  - flags["math_error"] → True when the check fails
  - math_error_detail  → human-readable string explaining the discrepancy
"""

from typing import Any

from src.layer1_parser.schema import ParsedFile

MATH_ERROR_TOLERANCE = 0.01  # 1 %


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _check_row(row: dict) -> None:
    """Validate one row dict in-place. Adds math_error_detail key."""
    flags = row["flags"]

    # ── Skip conditions ──────────────────────────────────────────────────────
    if flags.get("existing_equipment") or flags.get("not_in_total"):
        row["math_error_detail"] = ""
        return

    qty = row["quantity"]
    unit_price = row["unit_price"]
    total_price = row["total_price"]

    if not _is_number(unit_price) or not _is_number(total_price):
        row["math_error_detail"] = ""
        return

    if qty == 0:
        row["math_error_detail"] = ""
        return

    # ── Arithmetic check ─────────────────────────────────────────────────────
    computed = qty * unit_price
    stated = float(total_price)

    if stated == 0:
        # Can't use percentage; flag only when computed is also non-zero
        if abs(computed) > 0.01:
            flags["math_error"] = True
            row["math_error_detail"] = (
                f"total_price is 0 but {qty} × {unit_price} = {computed:.2f}"
            )
        else:
            row["math_error_detail"] = ""
        return

    relative_error = abs(computed - stated) / abs(stated)
    if relative_error > MATH_ERROR_TOLERANCE:
        flags["math_error"] = True
        row["math_error_detail"] = (
            f"{qty} × {unit_price} = {computed:.2f}, "
            f"stated {stated:.2f} "
            f"(Δ {computed - stated:+.2f}, {relative_error * 100:.1f}%)"
        )
    else:
        row["math_error_detail"] = ""


def validate_file(parsed_file: ParsedFile) -> dict:
    """Run math validation across every row.

    Returns the file as a plain dict with flags["math_error"] and
    math_error_detail populated where relevant.
    """
    data = parsed_file.model_dump()
    for sheet in data["sheets"]:
        for row in sheet["rows"]:
            _check_row(row)
    return data


# ── Quick smoke-test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    path = "data/processed/proj_2026_001/parsed_contractor_a.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # Re-parse through Pydantic so the model is clean
    from src.layer1_parser.schema import ParsedFile as PF
    pf = PF.model_validate(raw)
    result = validate_file(pf)

    errors = [
        (sheet["sheet_name"], row["row_index"], row["math_error_detail"])
        for sheet in result["sheets"]
        for row in sheet["rows"]
        if row["flags"]["math_error"]
    ]

    if errors:
        print(f"{'Sheet':<45} {'Row':<4}  Detail")
        print("-" * 100)
        for sheet_name, row_idx, detail in errors:
            print(f"{sheet_name:<45} {row_idx:<4}  {detail}")
    else:
        print("No math errors found in contractor_a data.")
