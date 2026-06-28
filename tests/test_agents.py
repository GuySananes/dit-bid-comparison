"""Tests for Layer 3 agents.

Rule: zero real Anthropic API calls.  Every test patches call_llm at the
import site *inside* the module under test, not at the origin in llm_client.

VectorStore is replaced with a MagicMock wherever agents accept it as an arg.
For agents C and D (which write files), _OUTPUT_ROOT is patched via monkeypatch
so tests write to pytest's tmp_path and leave no side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.layer3_agents.agent_a_ambiguity import resolve_ambiguities
from src.layer3_agents.agent_b_deviation import review_file
from src.layer3_agents.agent_c_ref_sheet import generate_ref_sheet
from src.layer3_agents.agent_d_summary import generate_summary


# ── shared builder helpers ────────────────────────────────────────────────────

def _meta(contractor_id: str = "c1", project_id: str = "p1") -> dict:
    return {
        "contractor_id": contractor_id,
        "project_id": project_id,
        "contractor_name": "קבלן בדיקה",
        "project_name": "פרויקט בדיקה",
        "file_name": "test.xlsx",
        "parsed_at": datetime.now(timezone.utc).isoformat(),
    }


def _row(
    row_index: int = 1,
    description: str = "מסך 65 אינץ",
    quantity: float = 1.0,
    unit_price: float = 5000.0,
    total_price: float = 5000.0,
    manufacturer_model: str = "Poly X52",
    mkt_status: str = "matched",
    requires_agent: bool = False,
    specs_confidence: float = 0.0,
    math_error: bool = False,
    technical_review: dict | None = None,
) -> dict:
    row: dict = {
        "row_index": row_index,
        "description": description,
        "unit": "יח",
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "manufacturer_model": manufacturer_model,
        "mkt_raw": "",
        "notes": "",
        "mkt_normalized": "polyx52",
        "flags": {
            "existing_equipment": False,
            "not_in_total": False,
            "optional": False,
            "math_error": math_error,
        },
        "mkt_match": {
            "status": mkt_status,
            "matched_to": "polyx52" if mkt_status == "matched" else None,
            "similarity_score": 0.95 if mkt_status == "matched" else 0.72,
            "method": "embedding",
            "requires_agent": requires_agent,
        },
        "specs_extracted": {
            "screen_size_inch": 65.0 if specs_confidence > 0 else None,
            "brightness_nit": None,
            "resolution": None,
            "response_time_ms": None,
            "work_hours": None,
            "hdmi_inputs": None,
            "camera_zoom_x": None,
            "raw_parse_confidence": specs_confidence,
        },
    }
    if technical_review:
        row["technical_review"] = technical_review
    return row


def _data(
    rows: list | None = None,
    contractor_id: str = "c1",
    project_id: str = "p1",
) -> dict:
    return {
        "meta": _meta(contractor_id, project_id),
        "sheets": [{"sheet_name": "חדר ישיבות", "rows": rows or [_row()]}],
    }


def _store() -> MagicMock:
    s = MagicMock()
    s.query_decisions.return_value = []
    s.query_mkt.return_value = []
    return s


def _deviation_review(severity: str = "major") -> dict:
    return {
        "deviation_detected": True,
        "severity": severity,
        "deviating_fields": ["brightness_nit"],
        "reasoning": "ספק הציע 330 NIT במקום 500 NIT",
        "recommendation": "request_replacement",
        "rag_sources_used": [],
    }


# ── Agent A — MKT ambiguity resolution ───────────────────────────────────────

_A = "src.layer3_agents.agent_a_ambiguity.call_llm"


class TestAgentA:
    def test_no_uncertain_rows_skips_llm(self):
        data = _data(rows=[_row(mkt_status="matched", requires_agent=False)])
        with patch(_A) as mock_llm:
            resolve_ambiguities(data, _store())
        mock_llm.assert_not_called()

    def test_uncertain_row_triggers_llm(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": True, "confidence": "high",
                 "reasoning": "same product", "normalized_name": "polyx52"}]
        with patch(_A, return_value=resp) as mock_llm:
            resolve_ambiguities(data, _store())
        mock_llm.assert_called_once()

    def test_same_product_sets_status_matched(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": True, "confidence": "high",
                 "reasoning": "same product", "normalized_name": "polyx52"}]
        with patch(_A, return_value=resp):
            result = resolve_ambiguities(data, _store())
        match = result["sheets"][0]["rows"][0]["mkt_match"]
        assert match["status"] == "matched"
        assert match["method"] == "agent_a"
        assert match["requires_agent"] is False

    def test_different_product_sets_status_no_match(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": False, "confidence": "high",
                 "reasoning": "different model number", "normalized_name": ""}]
        with patch(_A, return_value=resp):
            result = resolve_ambiguities(data, _store())
        match = result["sheets"][0]["rows"][0]["mkt_match"]
        assert match["status"] == "no_match"
        assert match["requires_agent"] is False

    def test_high_confidence_match_written_to_store(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": True, "confidence": "high",
                 "reasoning": "same product", "normalized_name": "polyx52"}]
        store = _store()
        with patch(_A, return_value=resp):
            resolve_ambiguities(data, store)
        store.add_mkt.assert_called_once()

    def test_medium_confidence_match_written_to_store(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": True, "confidence": "medium",
                 "reasoning": "likely same", "normalized_name": "polyx52"}]
        store = _store()
        with patch(_A, return_value=resp):
            resolve_ambiguities(data, store)
        store.add_mkt.assert_called_once()

    def test_low_confidence_not_written_to_store(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": True, "confidence": "low",
                 "reasoning": "maybe", "normalized_name": "polyx52"}]
        store = _store()
        with patch(_A, return_value=resp):
            resolve_ambiguities(data, store)
        store.add_mkt.assert_not_called()

    def test_no_match_decision_not_written_to_store(self):
        data = _data(rows=[_row(mkt_status="uncertain", requires_agent=True)])
        resp = [{"index": 0, "is_same_product": False, "confidence": "high",
                 "reasoning": "different", "normalized_name": ""}]
        store = _store()
        with patch(_A, return_value=resp):
            resolve_ambiguities(data, store)
        store.add_mkt.assert_not_called()

    def test_multiple_uncertain_rows_resolved_in_one_batch(self):
        rows = [_row(row_index=i, mkt_status="uncertain", requires_agent=True)
                for i in range(3)]
        data = _data(rows=rows)
        resp = [{"index": i, "is_same_product": True, "confidence": "high",
                 "reasoning": "ok", "normalized_name": "polyx52"}
                for i in range(3)]
        with patch(_A, return_value=resp) as mock_llm:
            result = resolve_ambiguities(data, _store())
        mock_llm.assert_called_once()
        for row in result["sheets"][0]["rows"]:
            assert row["mkt_match"]["status"] == "matched"

    def test_already_matched_rows_untouched(self):
        """Rows that are already matched must not be re-processed."""
        data = _data(rows=[
            _row(row_index=1, mkt_status="matched", requires_agent=False),
            _row(row_index=2, mkt_status="uncertain", requires_agent=True),
        ])
        resp = [{"index": 0, "is_same_product": True, "confidence": "high",
                 "reasoning": "ok", "normalized_name": "polyx52"}]
        with patch(_A, return_value=resp):
            result = resolve_ambiguities(data, _store())
        # Row 1 stays matched; row 2 gets updated
        assert result["sheets"][0]["rows"][0]["mkt_match"]["status"] == "matched"
        assert result["sheets"][0]["rows"][1]["mkt_match"]["method"] == "agent_a"


# ── Agent B — technical deviation review ─────────────────────────────────────

_B = "src.layer3_agents.agent_b_deviation.call_llm"


class TestAgentB:
    def test_ineligible_rows_skip_llm(self):
        """Rows with specs_confidence == 0 must not trigger an LLM call."""
        data = _data(rows=[_row(specs_confidence=0.0)])
        with patch(_B) as mock_llm:
            review_file(data, _store())
        mock_llm.assert_not_called()

    def test_eligible_row_triggers_llm(self):
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": False, "severity": "none",
                 "deviating_fields": [], "reasoning": "meets spec",
                 "recommendation": "accept", "rag_sources_used": []}]
        with patch(_B, return_value=resp) as mock_llm:
            review_file(data, _store())
        mock_llm.assert_called_once()

    def test_no_deviation_result_shape(self):
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": False, "severity": "none",
                 "deviating_fields": [], "reasoning": "meets spec",
                 "recommendation": "accept", "rag_sources_used": []}]
        with patch(_B, return_value=resp):
            result = review_file(data, _store())
        review = result["sheets"][0]["rows"][0]["technical_review"]
        assert review["deviation_detected"] is False
        assert review["severity"] == "none"
        assert review["recommendation"] == "accept"

    def test_major_deviation_result_shape(self):
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": True, "severity": "major",
                 "deviating_fields": ["brightness_nit"],
                 "reasoning": "330 NIT vs 500 NIT required",
                 "recommendation": "request_replacement", "rag_sources_used": []}]
        with patch(_B, return_value=resp):
            result = review_file(data, _store())
        review = result["sheets"][0]["rows"][0]["technical_review"]
        assert review["deviation_detected"] is True
        assert review["severity"] == "major"
        assert "brightness_nit" in review["deviating_fields"]

    def test_major_deviation_written_to_store(self):
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": True, "severity": "major",
                 "deviating_fields": ["brightness_nit"], "reasoning": "too dim",
                 "recommendation": "request_replacement", "rag_sources_used": []}]
        store = _store()
        with patch(_B, return_value=resp):
            review_file(data, store)
        store.add_decision.assert_called_once()

    def test_no_deviation_not_written_to_store(self):
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": False, "severity": "none",
                 "deviating_fields": [], "reasoning": "ok",
                 "recommendation": "accept", "rag_sources_used": []}]
        store = _store()
        with patch(_B, return_value=resp):
            review_file(data, store)
        store.add_decision.assert_not_called()

    def test_minor_deviation_written_to_store(self):
        """Any non-none severity with deviation_detected=True is stored (minor included)."""
        data = _data(rows=[_row(specs_confidence=0.14)])
        resp = [{"index": 0, "deviation_detected": True, "severity": "minor",
                 "deviating_fields": ["response_time_ms"], "reasoning": "slightly slow",
                 "recommendation": "accept_with_note", "rag_sources_used": []}]
        store = _store()
        with patch(_B, return_value=resp):
            review_file(data, store)
        store.add_decision.assert_called_once()

    def test_rag_queried_once_per_eligible_row(self):
        rows = [_row(row_index=i, specs_confidence=0.14) for i in range(3)]
        data = _data(rows=rows)
        resp = [{"index": i, "deviation_detected": False, "severity": "none",
                 "deviating_fields": [], "reasoning": "ok",
                 "recommendation": "accept", "rag_sources_used": []}
                for i in range(3)]
        store = _store()
        with patch(_B, return_value=resp):
            review_file(data, store)
        assert store.query_decisions.call_count == 3

    def test_ineligible_rows_have_no_technical_review(self):
        data = _data(rows=[_row(specs_confidence=0.0)])
        with patch(_B):
            result = review_file(data, _store())
        assert "technical_review" not in result["sheets"][0]["rows"][0]


# ── Agent C — contractor ref sheet ───────────────────────────────────────────

_C = "src.layer3_agents.agent_c_ref_sheet.call_llm"
_C_ROOT = "src.layer3_agents.agent_c_ref_sheet._OUTPUT_ROOT"
_LETTER = "מכתב פנייה לקבלן\n\n1. שגיאת חשבון בשורה 1\n2. מק\"ט לא מזוהה"


class TestAgentC:
    def test_no_flagged_rows_returns_none(self):
        data = _data(rows=[_row()])  # no flags set
        with patch(_C) as mock_llm:
            result = generate_ref_sheet(data)
        assert result is None
        mock_llm.assert_not_called()

    def test_math_error_row_triggers_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)])
        with patch(_C, return_value=_LETTER):
            result = generate_ref_sheet(data)
        assert result is not None

    def test_unknown_mkt_row_triggers_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(mkt_status="no_match")])
        with patch(_C, return_value=_LETTER):
            result = generate_ref_sheet(data)
        assert result is not None

    def test_tech_deviation_row_triggers_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(technical_review=_deviation_review("major"))])
        with patch(_C, return_value=_LETTER):
            result = generate_ref_sheet(data)
        assert result is not None

    def test_minor_deviation_row_triggers_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(technical_review=_deviation_review("minor"))])
        with patch(_C, return_value=_LETTER):
            result = generate_ref_sheet(data)
        assert result is not None

    def test_output_path_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)], contractor_id="c1", project_id="p1")
        with patch(_C, return_value=_LETTER):
            path = generate_ref_sheet(data)
        p = Path(path)
        assert p.exists()
        assert "p1" in str(p)           # project_id in dir
        assert "ref_sheet_c1" in p.name  # contractor_id in filename
        assert p.suffix == ".md"

    def test_file_content_equals_llm_response(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)])
        with patch(_C, return_value=_LETTER):
            path = generate_ref_sheet(data)
        assert Path(path).read_text(encoding="utf-8") == _LETTER

    def test_contractor_name_in_llm_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)])
        data["meta"]["contractor_name"] = "קבלן א"
        with patch(_C, return_value=_LETTER) as mock_llm:
            generate_ref_sheet(data)
        user_msg = mock_llm.call_args[0][1]
        assert "קבלן א" in user_msg

    def test_project_name_in_llm_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)])
        data["meta"]["project_name"] = "פרויקט ב"
        with patch(_C, return_value=_LETTER) as mock_llm:
            generate_ref_sheet(data)
        user_msg = mock_llm.call_args[0][1]
        assert "פרויקט ב" in user_msg

    def test_expect_json_false(self, tmp_path, monkeypatch):
        """Agent C must call LLM with expect_json=False (output is prose)."""
        monkeypatch.setattr(_C_ROOT, str(tmp_path))
        data = _data(rows=[_row(math_error=True)])
        with patch(_C, return_value=_LETTER) as mock_llm:
            generate_ref_sheet(data)
        _, kwargs = mock_llm.call_args
        assert kwargs.get("expect_json") is False


# ── Agent D — executive summary ───────────────────────────────────────────────

_D = "src.layer3_agents.agent_d_summary.call_llm"
_D_ROOT = "src.layer3_agents.agent_d_summary._OUTPUT_ROOT"
_SUMMARY = "# סיכום הנהלה\n\nהצעות מחיר התקבלו מ-2 קבלנים.\n\n## המלצות"


def _two_files() -> list[dict]:
    return [
        _data(
            contractor_id="c1",
            rows=[_row(row_index=1, total_price=50000.0, specs_confidence=0.14,
                       technical_review=_deviation_review("major"))],
        ),
        _data(
            contractor_id="c2",
            rows=[_row(row_index=1, total_price=48000.0)],
        ),
    ]


class TestAgentD:
    def test_raises_on_empty_input(self):
        with pytest.raises(ValueError):
            generate_summary([], "p1")

    def test_output_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY):
            path = generate_summary(_two_files(), "p1")
        assert Path(path).exists()

    def test_output_filename(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY):
            path = generate_summary(_two_files(), "p1")
        assert Path(path).name == "executive_summary.md"

    def test_output_in_project_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY):
            path = generate_summary(_two_files(), "proj_xyz")
        assert "proj_xyz" in str(path)

    def test_file_content_equals_llm_response(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY):
            path = generate_summary(_two_files(), "p1")
        assert Path(path).read_text(encoding="utf-8") == _SUMMARY

    def test_project_name_in_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1", "שם הפרויקט")
        user_msg = mock_llm.call_args[0][1]
        assert "שם הפרויקט" in user_msg

    def test_contractor_count_in_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1")
        user_msg = mock_llm.call_args[0][1]
        assert "2" in user_msg

    def test_totals_in_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1")
        user_msg = mock_llm.call_args[0][1]
        assert "50000" in user_msg   # c1 total (50000.0 serialised as "50000.0")
        assert "48000" in user_msg   # c2 total

    def test_major_deviation_in_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1")
        user_msg = mock_llm.call_args[0][1]
        assert "major" in user_msg

    def test_completeness_in_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1")
        user_msg = mock_llm.call_args[0][1]
        assert "overall" in user_msg

    def test_disqualifying_severity_excluded_from_minor_check(self, tmp_path, monkeypatch):
        """Disqualifying deviations must also appear in the deviations list."""
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        files = [
            _data(rows=[_row(specs_confidence=0.14,
                             technical_review=_deviation_review("disqualifying"))]),
        ]
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(files, "p1")
        user_msg = mock_llm.call_args[0][1]
        assert "disqualifying" in user_msg

    def test_expect_json_false(self, tmp_path, monkeypatch):
        """Agent D must call LLM with expect_json=False (output is prose)."""
        monkeypatch.setattr(_D_ROOT, str(tmp_path))
        with patch(_D, return_value=_SUMMARY) as mock_llm:
            generate_summary(_two_files(), "p1")
        _, kwargs = mock_llm.call_args
        assert kwargs.get("expect_json") is False
