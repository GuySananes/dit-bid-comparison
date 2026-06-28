"""Tests for Layer 2 normalization modules.

Covers:
- text_normalizer.normalize_mkt  — key cases from the README + edge cases
- spec_extractor.extract_specs   — all seven field types
- math_validator.validate_file   — error detection and every skip condition
"""

from datetime import datetime, timezone

import pytest

from src.layer1_parser.schema import FileMeta, ParsedFile, ParsedRow, ParsedSheet, RowFlags
from src.layer2_normalization.math_validator import validate_file
from src.layer2_normalization.spec_extractor import extract_specs
from src.layer2_normalization.text_normalizer import normalize_mkt


# ── test helpers ──────────────────────────────────────────────────────────────

def _file(rows: list[ParsedRow]) -> ParsedFile:
    return ParsedFile(
        meta=FileMeta(
            contractor_id="c1",
            file_name="test.xlsx",
            project_id="p1",
            parsed_at=datetime.now(timezone.utc),
        ),
        sheets=[ParsedSheet(sheet_name="חדר ישיבות", rows=rows, sheet_total=0.0)],
    )


def _row(**kwargs) -> ParsedRow:
    base = dict(
        row_index=1,
        description="item",
        unit="יח",
        quantity=1.0,
        unit_price=1000.0,
        total_price=1000.0,
        manufacturer_model="",
        mkt_raw="",
        notes="",
        flags=RowFlags(),
    )
    base.update(kwargs)
    return ParsedRow(**base)


def _validated_row(**kwargs) -> dict:
    """Return the first row dict after running validate_file."""
    return validate_file(_file([_row(**kwargs)]))["sheets"][0]["rows"][0]


# ── normalize_mkt ─────────────────────────────────────────────────────────────

class TestNormalizeMkt:
    # README canonical examples
    def test_poly_bundle_matches_bare_model(self):
        assert normalize_mkt("POLY X52") == normalize_mkt("Poly Studio X52 + TC10 + EX MIC")

    def test_polycom_alias_matches_poly(self):
        assert normalize_mkt("polycom studio x52 bundle") == normalize_mkt("POLY X52")

    def test_poly_different_model_numbers_differ(self):
        assert normalize_mkt("POLY X52") != normalize_mkt("POLY X72")

    def test_samsung_dash_stripped(self):
        assert normalize_mkt("SAMSUNG QB65C-N") == normalize_mkt("samsung qb65cn")

    def test_msolutions_spacing_and_dash(self):
        assert normalize_mkt("Msolutions MS-070") == normalize_mkt("M Solutions MS070")

    # Brand alias
    def test_polycom_normalised_to_poly(self):
        result = normalize_mkt("Polycom X52")
        assert result.startswith("poly")
        assert "polycom" not in result

    # Noise words
    def test_noise_words_stripped(self):
        # "professional" and "series" are noise — output identical without them
        assert normalize_mkt("Sony Professional Series A95L") == normalize_mkt("Sony A95L")

    def test_bundle_noise_word_stripped(self):
        assert normalize_mkt("Poly X52 Bundle") == normalize_mkt("Poly X52")

    # Poly-specific logic
    def test_poly_tc_standalone_retained(self):
        # TC10 without an X/G codec is the product itself, not an accessory
        result = normalize_mkt("Poly TC10")
        assert "tc10" in result

    def test_poly_x_series_takes_priority_over_tc(self):
        # X52 is the codec; TC10 is an accessory — output is polyx52
        assert normalize_mkt("Poly X52 TC10") == normalize_mkt("Poly X52")

    # Edge cases
    def test_empty_string(self):
        assert normalize_mkt("") == ""

    def test_whitespace_only(self):
        assert normalize_mkt("   ") == ""

    def test_output_is_lowercase(self):
        result = normalize_mkt("Samsung QM55C")
        assert result == result.lower()

    def test_special_chars_removed(self):
        # Hyphens, quotes, dots must not appear in output
        result = normalize_mkt('Sony "Bravia" A95L-Pro')
        assert '"' not in result
        assert "-" not in result
        assert "." not in result

    def test_multiline_input_uses_first_line(self):
        # manufacturer_model sometimes contains newlines — only first line matters
        result = normalize_mkt("Poly X52\nTC10 accessory")
        assert normalize_mkt("Poly X52") == result


# ── spec_extractor ────────────────────────────────────────────────────────────

class TestExtractSpecs:
    # screen_size_inch
    def test_screen_size_hebrew_suffix(self):
        assert extract_specs("מסך 65 אינץ' LED")["screen_size_inch"] == 65.0

    def test_screen_size_quote_suffix(self):
        assert extract_specs('Display 86" 4K')["screen_size_inch"] == 86.0

    def test_screen_size_inch_english(self):
        assert extract_specs("75 inch display")["screen_size_inch"] == 75.0

    # brightness_nit
    def test_brightness_nit_uppercase(self):
        assert extract_specs("500NIT display")["brightness_nit"] == 500

    def test_brightness_nit_lowercase_with_space(self):
        assert extract_specs("350 nit brightness")["brightness_nit"] == 350

    # resolution
    def test_resolution_4k_uHD_label(self):
        assert extract_specs("מסך 4K UHD")["resolution"] == "4K UHD"

    def test_resolution_pixel_dimensions(self):
        assert extract_specs("3840*2160 display")["resolution"] == "3840x2160"

    def test_resolution_fhd(self):
        assert extract_specs("FHD monitor")["resolution"] == "FHD"

    def test_resolution_4k_without_uHD(self):
        assert extract_specs("4K display")["resolution"] == "4K"

    # response_time_ms
    def test_response_time_g_to_g(self):
        assert extract_specs("G TO G 8MS response")["response_time_ms"] == 8

    def test_response_time_simple(self):
        assert extract_specs("4ms response")["response_time_ms"] == 4

    # work_hours
    def test_work_hours_16_7(self):
        assert extract_specs("פעולה 16/7")["work_hours"] == "16/7"

    def test_work_hours_24_7(self):
        assert extract_specs("24/7 operation")["work_hours"] == "24/7"

    # hdmi_inputs
    def test_hdmi_hebrew(self):
        assert extract_specs("2 כניסות HDMI")["hdmi_inputs"] == 2

    def test_hdmi_english_x_suffix(self):
        assert extract_specs("HDMI x3")["hdmi_inputs"] == 3

    # camera_zoom_x
    def test_camera_zoom_x_prefix(self):
        assert extract_specs("PTZ zoomX12 camera")["camera_zoom_x"] == 12

    def test_camera_zoom_number_first(self):
        assert extract_specs("12X zoom PTZ")["camera_zoom_x"] == 12

    # raw_parse_confidence
    def test_no_specs_confidence_zero(self):
        assert extract_specs("כבל HDMI")["raw_parse_confidence"] == 0.0

    def test_one_field_confidence_nonzero(self):
        s = extract_specs("65 inch display")
        assert s["raw_parse_confidence"] > 0.0

    def test_two_fields_higher_confidence_than_one(self):
        one = extract_specs("65 inch")
        two = extract_specs("65 inch 500NIT")
        assert two["raw_parse_confidence"] > one["raw_parse_confidence"]

    def test_all_keys_always_present(self):
        s = extract_specs("")
        assert set(s.keys()) == {
            "screen_size_inch", "brightness_nit", "resolution",
            "response_time_ms", "work_hours", "hdmi_inputs",
            "camera_zoom_x", "raw_parse_confidence",
        }

    def test_missing_fields_are_none(self):
        s = extract_specs("65 inch display")
        assert s["brightness_nit"] is None
        assert s["resolution"] is None


# ── math_validator ────────────────────────────────────────────────────────────

class TestMathValidator:
    # README case: 3 × 4500 = 13500 ≠ 13000
    def test_math_error_detected(self):
        row = _validated_row(quantity=3.0, unit_price=4500.0, total_price=13000.0)
        assert row["flags"]["math_error"] is True

    def test_math_error_detail_populated(self):
        row = _validated_row(quantity=3.0, unit_price=4500.0, total_price=13000.0)
        assert row["math_error_detail"] != ""

    def test_exact_match_no_error(self):
        row = _validated_row(quantity=3.0, unit_price=4500.0, total_price=13500.0)
        assert row["flags"]["math_error"] is False

    def test_within_one_percent_no_error(self):
        # 1000 × 1 = 1000; 1005 is 0.5% off → within tolerance
        row = _validated_row(quantity=1.0, unit_price=1000.0, total_price=1005.0)
        assert row["flags"]["math_error"] is False

    def test_just_over_tolerance_flagged(self):
        # 1000 × 1 = 1000; 985 is 1.5% off → error
        row = _validated_row(quantity=1.0, unit_price=1000.0, total_price=985.0)
        assert row["flags"]["math_error"] is True

    def test_no_error_detail_when_correct(self):
        row = _validated_row(quantity=1.0, unit_price=1000.0, total_price=1000.0)
        assert row["math_error_detail"] == ""

    # Skip conditions
    def test_skip_existing_equipment(self):
        row = _validated_row(
            quantity=2.0, unit_price=1000.0, total_price=9999.0,
            flags=RowFlags(existing_equipment=True),
        )
        assert row["flags"]["math_error"] is False

    def test_skip_not_in_total(self):
        row = _validated_row(
            quantity=2.0, unit_price=1000.0, total_price=9999.0,
            flags=RowFlags(not_in_total=True),
        )
        assert row["flags"]["math_error"] is False

    def test_skip_string_unit_price(self):
        row = _validated_row(quantity=2.0, unit_price="ציוד קיים", total_price=5000.0)
        assert row["flags"]["math_error"] is False

    def test_skip_string_total_price(self):
        row = _validated_row(quantity=2.0, unit_price=1000.0, total_price="לא לסיכום")
        assert row["flags"]["math_error"] is False

    def test_skip_zero_quantity(self):
        row = _validated_row(quantity=0.0, unit_price=1000.0, total_price=9999.0)
        assert row["flags"]["math_error"] is False

    # Multi-row file
    def test_only_bad_row_flagged_in_multi_row_file(self):
        rows = [
            _row(row_index=1, quantity=1.0, unit_price=1000.0, total_price=1000.0),  # OK
            _row(row_index=2, quantity=3.0, unit_price=4500.0, total_price=13000.0),  # error
        ]
        result = validate_file(_file(rows))
        sheet_rows = result["sheets"][0]["rows"]
        assert sheet_rows[0]["flags"]["math_error"] is False
        assert sheet_rows[1]["flags"]["math_error"] is True
