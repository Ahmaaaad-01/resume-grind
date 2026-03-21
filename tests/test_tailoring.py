"""Tests for src/tailoring.py — validation logic and Claude API integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tailoring import (
    _build_user_prompt,
    tailor_resume,
    validate_tailored_output,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bank():
    with open(FIXTURES_DIR / "fake_resume_bank.json") as f:
        return json.load(f)


@pytest.fixture
def valid_tailored():
    """A valid tailored output matching the fake bank."""
    return {
        "summary_used": "sum-consumer",
        "summary_text_final": "Product Manager with 2 years of experience.",
        "experience": [
            {
                "role_id": "role-ex1",
                "bullets_selected": [
                    {
                        "source_ids": ["b01"],
                        "tier": "rewritten",
                        "text_final": "Led development of a mobile checkout feature used by 500K+ monthly users",
                        "derivation_rationale": None,
                        "modification": "reframed for JD emphasis on mobile",
                        "jd_relevance": 9,
                    },
                    {
                        "source_ids": ["b02"],
                        "tier": "rewritten",
                        "text_final": "Designed and ran A/B experiments on onboarding flow, improving 7-day retention by 12%",
                        "derivation_rationale": None,
                        "modification": "reframed for experimentation focus",
                        "jd_relevance": 8,
                    },
                    {
                        "source_ids": ["b03"],
                        "tier": "rewritten",
                        "text_final": "Wrote PRDs for 4 feature releases",
                        "derivation_rationale": None,
                        "modification": "none",
                        "jd_relevance": 6,
                    },
                ],
            }
        ],
        "skills_order": [
            {"original": "SQL", "display": "SQL"},
            {"original": "A/B Testing", "display": "A/B Testing & Experimentation"},
            {"original": "Agile / Scrum", "display": "Agile Methodology"},
        ],
        "project_included": None,
        "gaps": ["JD asks for fintech experience"],
    }


# ---------------------------------------------------------------------------
# validate_tailored_output — valid cases
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_output_no_errors(self, bank, valid_tailored):
        errors = validate_tailored_output(valid_tailored, bank)
        assert errors == []

    def test_empty_experience_ok(self, bank):
        tailored = {
            "summary_used": "sum-consumer",
            "experience": [],
        }
        errors = validate_tailored_output(tailored, bank)
        assert errors == []


# ---------------------------------------------------------------------------
# validate_tailored_output — source_id checks
# ---------------------------------------------------------------------------

class TestSourceIdValidation:
    def test_invalid_source_id(self, bank, valid_tailored):
        valid_tailored["experience"][0]["bullets_selected"][0]["source_ids"] = ["b99"]
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("b99" in e and "INVALID source_id" in e for e in errors)

    def test_invalid_role_id(self, bank, valid_tailored):
        valid_tailored["experience"][0]["role_id"] = "role-fake"
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("INVALID role_id" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_tailored_output — rewritten / backward-compat tier rules
# ---------------------------------------------------------------------------

class TestRewrittenValidation:
    def test_rewritten_must_have_one_source(self, bank, valid_tailored):
        valid_tailored["experience"][0]["bullets_selected"][0]["source_ids"] = ["b01", "b02"]
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("REWRITTEN" in e and "exactly 1" in e for e in errors)

    def test_rewritten_zero_sources(self, bank, valid_tailored):
        valid_tailored["experience"][0]["bullets_selected"][0]["source_ids"] = []
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("REWRITTEN" in e and "exactly 1" in e for e in errors)

    def test_backward_compat_selected_tier(self, bank, valid_tailored):
        """Old 'selected' tier still validates."""
        valid_tailored["experience"][0]["bullets_selected"][0]["tier"] = "selected"
        errors = validate_tailored_output(valid_tailored, bank)
        assert errors == []

    def test_backward_compat_rephrased_tier(self, bank, valid_tailored):
        """Old 'rephrased' tier still validates."""
        valid_tailored["experience"][0]["bullets_selected"][0]["tier"] = "rephrased"
        errors = validate_tailored_output(valid_tailored, bank)
        assert errors == []

    def test_backward_compat_selected_must_have_one_source(self, bank, valid_tailored):
        valid_tailored["experience"][0]["bullets_selected"][0]["tier"] = "selected"
        valid_tailored["experience"][0]["bullets_selected"][0]["source_ids"] = ["b01", "b02"]
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("SELECTED" in e and "exactly 1" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_tailored_output — derived bullet rules
# ---------------------------------------------------------------------------

class TestDerivedValidation:
    def _make_derived(self, source_ids, rationale="Valid rationale"):
        return {
            "source_ids": source_ids,
            "tier": "derived",
            "text_final": "Derived bullet text",
            "derivation_rationale": rationale,
            "modification": "synthesized",
        }

    def test_valid_derived_bullet(self, bank, valid_tailored):
        derived = self._make_derived(["b01", "b03"])
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert errors == []

    def test_derived_max_3_sources(self, bank, valid_tailored):
        derived = self._make_derived(["b01", "b02", "b03"])
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert errors == []  # 3 sources is fine

    def test_derived_too_many_sources(self, bank, valid_tailored):
        derived = self._make_derived(["b01", "b02", "b03", "b04"])
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("4 source_ids" in e for e in errors)

    def test_derived_zero_sources(self, bank, valid_tailored):
        derived = self._make_derived([])
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("0 source_ids" in e for e in errors)

    def test_derived_missing_rationale(self, bank, valid_tailored):
        derived = self._make_derived(["b01", "b02"], rationale=None)
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("missing derivation_rationale" in e for e in errors)

    def test_derived_empty_rationale(self, bank, valid_tailored):
        derived = self._make_derived(["b01", "b02"], rationale="")
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("missing derivation_rationale" in e for e in errors)

    def test_no_derived_cap(self, bank, valid_tailored):
        """Derived bullets have no artificial cap — 10+ should pass."""
        for i in range(10):
            derived = self._make_derived(["b01"], rationale=f"Rationale {i}")
            valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert not any("EXCEEDED" in e for e in errors)

    def test_derived_cross_role_reference(self, bank, valid_tailored):
        """Derived bullet referencing a bullet from a different role."""
        # Add a second role with its own bullets
        bank["experience"].append({
            "role_id": "role-ex2",
            "company": "Other Corp",
            "title": "Analyst",
            "start_date": "2022-01",
            "end_date": "2023-12",
            "location": "NYC",
            "include_always": False,
            "bullets": [
                {"id": "b10", "text": "Other bullet", "tags": ["other"],
                 "has_metric": False, "metric_value": None, "priority": 2},
            ],
        })
        # Derive from b01 (role-ex1) while in role-ex1 context — valid
        derived = self._make_derived(["b01"], rationale="Same role")
        valid_tailored["experience"][0]["bullets_selected"].append(derived)
        errors = validate_tailored_output(valid_tailored, bank)
        assert not any("different role" in e for e in errors)

        # Derive from b10 (role-ex2) while in role-ex1 context — invalid
        derived2 = self._make_derived(["b10"], rationale="Cross role")
        valid_tailored["experience"][0]["bullets_selected"].append(derived2)
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("different role" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_tailored_output — summary validation
# ---------------------------------------------------------------------------

class TestSummaryValidation:
    def test_valid_summary_id(self, bank, valid_tailored):
        errors = validate_tailored_output(valid_tailored, bank)
        assert not any("summary_used" in e for e in errors)

    def test_invalid_summary_id(self, bank, valid_tailored):
        valid_tailored["summary_used"] = "sum-nonexistent"
        errors = validate_tailored_output(valid_tailored, bank)
        assert any("INVALID summary_used" in e for e in errors)

    def test_no_summary_used_ok(self, bank, valid_tailored):
        valid_tailored["summary_used"] = None
        errors = validate_tailored_output(valid_tailored, bank)
        assert not any("summary_used" in e for e in errors)


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_resume_bank(self, bank):
        config = {"tailoring": {"max_bullets_per_role": 5, "min_bullets_per_role": 3}}
        prompt = _build_user_prompt(bank, "Some JD text", config)
        assert "Alex Sample" in prompt
        assert "Some JD text" in prompt
        assert "b01" in prompt

    def test_contains_constraints(self, bank):
        config = {"tailoring": {
            "recent_jobs_bullet_limits": {"min": 3, "max": 7},
            "older_jobs_bullet_limits": {"max": 2},
        }}
        prompt = _build_user_prompt(bank, "JD", config)
        assert "3-7" in prompt
        assert "max 2" in prompt
        assert "RECENT" in prompt
        assert "Rewrite every bullet aggressively" in prompt

    def test_default_config_values(self, bank):
        prompt = _build_user_prompt(bank, "JD", {})
        assert "3-7" in prompt  # defaults
        assert "max 2" in prompt

    def test_jd_preamble_off_by_default(self, bank):
        config = {"tailoring": {}}
        prompt = _build_user_prompt(bank, "JD", config)
        assert "jd_analysis" not in prompt

    def test_jd_preamble_on(self, bank):
        config = {"tailoring": {"jd_analysis_preamble": True}}
        prompt = _build_user_prompt(bank, "JD", config)
        assert "jd_analysis" in prompt
        assert "requirements" in prompt


# ---------------------------------------------------------------------------
# tailor_resume — with mocked Claude API
# ---------------------------------------------------------------------------

class TestTailorResume:
    def _make_config(self):
        return {
            "tailoring": {
                "provider": "claude",
                "max_bullets_per_role": 5,
                "min_bullets_per_role": 3,
            }
        }

    @patch("src.tailoring._call_claude")
    def test_successful_tailoring(self, mock_call, bank):
        valid_response = {
            "summary_used": "sum-consumer",
            "summary_text_final": "Tailored summary.",
            "experience": [
                {
                    "role_id": "role-ex1",
                    "bullets_selected": [
                        {"source_ids": ["b01"], "tier": "rewritten",
                         "text_final": "Bullet 1", "derivation_rationale": None,
                         "modification": "reframed", "jd_relevance": 9},
                        {"source_ids": ["b02"], "tier": "rewritten",
                         "text_final": "Bullet 2", "derivation_rationale": None,
                         "modification": "reframed", "jd_relevance": 8},
                        {"source_ids": ["b03"], "tier": "rewritten",
                         "text_final": "Bullet 3", "derivation_rationale": None,
                         "modification": "reframed", "jd_relevance": 7},
                    ],
                }
            ],
            "skills_order": [{"original": "SQL", "display": "SQL"}],
            "project_included": None,
            "gaps": [],
        }
        mock_call.return_value = json.dumps(valid_response)

        result = tailor_resume(
            {"title_raw": "APM", "company": "TestCo"},
            "Some JD text",
            bank,
            self._make_config(),
        )
        assert result["validation_errors"] == []
        assert result["summary_used"] == "sum-consumer"

    @patch("src.tailoring._call_claude")
    def test_handles_markdown_fences(self, mock_call, bank):
        """LLM sometimes wraps JSON in markdown fences — we strip them."""
        valid_response = {
            "summary_used": "sum-data",
            "summary_text_final": "Summary.",
            "experience": [],
            "skills_order": [],
            "project_included": None,
            "gaps": [],
        }
        mock_call.return_value = f"```json\n{json.dumps(valid_response)}\n```"

        result = tailor_resume({}, "JD", bank, self._make_config())
        assert result["summary_used"] == "sum-data"
        assert result["validation_errors"] == []

    @patch("src.tailoring._call_claude")
    def test_handles_invalid_json(self, mock_call, bank):
        mock_call.return_value = "This is not JSON at all"

        result = tailor_resume({}, "JD", bank, self._make_config())
        assert len(result["validation_errors"]) > 0
        assert "invalid JSON" in result["validation_errors"][0]

    @patch("src.tailoring._call_claude")
    def test_validation_errors_attached(self, mock_call, bank):
        """Invalid source_ids in LLM response are caught by validation."""
        bad_response = {
            "summary_used": "sum-consumer",
            "summary_text_final": "Summary.",
            "experience": [
                {
                    "role_id": "role-ex1",
                    "bullets_selected": [
                        {"source_ids": ["b99"], "tier": "rewritten",
                         "text_final": "Bad bullet", "derivation_rationale": None,
                         "modification": "reframed", "jd_relevance": 5},
                    ],
                }
            ],
            "skills_order": [],
            "project_included": None,
            "gaps": [],
        }
        mock_call.return_value = json.dumps(bad_response)

        result = tailor_resume({}, "JD", bank, self._make_config())
        assert any("b99" in e for e in result["validation_errors"])


# ---------------------------------------------------------------------------
# Multiple errors in one validation
# ---------------------------------------------------------------------------

class TestMultipleErrors:
    def test_multiple_issues_all_reported(self, bank):
        tailored = {
            "summary_used": "sum-fake",
            "experience": [
                {
                    "role_id": "role-ex1",
                    "bullets_selected": [
                        # rewritten with 2 source_ids
                        {"source_ids": ["b01", "b02"], "tier": "rewritten",
                         "text_final": "Bad", "derivation_rationale": None,
                         "modification": "none"},
                        # derived with no rationale
                        {"source_ids": ["b01"], "tier": "derived",
                         "text_final": "Derived", "derivation_rationale": "",
                         "modification": "synthesized"},
                        # invalid source_id
                        {"source_ids": ["b99"], "tier": "rewritten",
                         "text_final": "Fake", "derivation_rationale": None,
                         "modification": "none"},
                    ],
                }
            ],
        }
        errors = validate_tailored_output(tailored, bank)
        assert len(errors) >= 3  # summary, rewritten count, derived rationale, invalid id


# ---------------------------------------------------------------------------
# Bullet count limits (recent vs older roles)
# ---------------------------------------------------------------------------

class TestBulletCountLimits:
    """Validate that bullet count limits are enforced for recent vs older roles."""

    @pytest.fixture
    def bank_with_dates(self, bank):
        """Bank with 3 roles: 2 recent (role-ex1, role-ex3) and 1 older (role-ex2)."""
        bank["experience"][0]["start_date"] = "2024-01"
        bank["experience"][0]["end_date"] = "present"
        bank["experience"].append({
            "role_id": "role-ex2",
            "company": "Old Corp",
            "title": "Intern",
            "start_date": "2020-01",
            "end_date": "2020-06",
            "location": "NYC",
            "include_always": False,
            "bullets": [
                {"id": "b10", "text": "Old bullet 1", "tags": ["old"],
                 "has_metric": False, "metric_value": None, "priority": 2},
                {"id": "b11", "text": "Old bullet 2", "tags": ["old"],
                 "has_metric": False, "metric_value": None, "priority": 2},
                {"id": "b12", "text": "Old bullet 3", "tags": ["old"],
                 "has_metric": False, "metric_value": None, "priority": 2},
            ],
        })
        # A second recent role to ensure role-ex2 is pushed to OLDER
        bank["experience"].append({
            "role_id": "role-ex3",
            "company": "Recent Corp",
            "title": "PM",
            "start_date": "2023-01",
            "end_date": "2024-01",
            "location": "NYC",
            "include_always": True,
            "bullets": [
                {"id": "b20", "text": "Recent bullet", "tags": ["recent"],
                 "has_metric": False, "metric_value": None, "priority": 2},
            ],
        })
        return bank

    def _make_bullet(self, sid):
        return {"source_ids": [sid], "tier": "rewritten",
                "text_final": f"Bullet from {sid}", "derivation_rationale": None,
                "modification": "reframed", "jd_relevance": 7}

    def test_recent_role_within_limits(self, bank_with_dates):
        """Recent role with 5 bullets passes validation."""
        tailored = {
            "summary_used": "sum-consumer",
            "experience": [{
                "role_id": "role-ex1",
                "bullets_selected": [self._make_bullet("b01") for _ in range(5)],
            }],
        }
        errors = validate_tailored_output(tailored, bank_with_dates)
        assert not any("RECENT" in e for e in errors)

    def test_recent_role_exceeds_max(self, bank_with_dates):
        """Recent role with 8 bullets (>7) triggers validation error."""
        tailored = {
            "summary_used": "sum-consumer",
            "experience": [{
                "role_id": "role-ex1",
                "bullets_selected": [self._make_bullet("b01") for _ in range(8)],
            }],
        }
        errors = validate_tailored_output(tailored, bank_with_dates)
        assert any("RECENT" in e and "8 bullets" in e for e in errors)

    def test_older_role_within_limits(self, bank_with_dates):
        """Older role with 2 bullets passes validation."""
        tailored = {
            "summary_used": "sum-consumer",
            "experience": [{
                "role_id": "role-ex2",
                "bullets_selected": [
                    self._make_bullet("b10"),
                    self._make_bullet("b11"),
                ],
            }],
        }
        errors = validate_tailored_output(tailored, bank_with_dates)
        assert not any("OLDER" in e for e in errors)

    def test_older_role_exceeds_max(self, bank_with_dates):
        """Older role with 3 bullets (>2) triggers validation error."""
        tailored = {
            "summary_used": "sum-consumer",
            "experience": [{
                "role_id": "role-ex2",
                "bullets_selected": [
                    self._make_bullet("b10"),
                    self._make_bullet("b11"),
                    self._make_bullet("b12"),
                ],
            }],
        }
        errors = validate_tailored_output(tailored, bank_with_dates)
        assert any("OLDER" in e and "3 bullets" in e for e in errors)
