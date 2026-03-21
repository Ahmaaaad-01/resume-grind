"""Tests for src/resume_bank.py — loading, validation, and helper functions."""

import copy
import json
from pathlib import Path

import pytest

from src.resume_bank import (
    get_all_bullet_ids,
    get_role_bullet_ids,
    load_resume_bank,
    validate_resume_bank,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def valid_bank():
    """Load the example resume bank as a valid baseline."""
    with open(FIXTURES_DIR / "fake_resume_bank.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Valid bank tests
# ---------------------------------------------------------------------------

class TestValidBank:
    def test_fixture_is_valid(self, valid_bank):
        errors = validate_resume_bank(valid_bank)
        assert errors == []

    def test_load_from_fixture(self):
        bank = load_resume_bank(FIXTURES_DIR / "fake_resume_bank.json")
        assert bank["meta"]["candidate_name"] == "Alex Sample"
        assert len(bank["experience"]) >= 1
        assert len(bank["summaries"]) >= 2

    def test_example_bank_is_valid(self):
        example_path = Path(__file__).parent.parent / "examples" / "resume_bank.example.json"
        bank = load_resume_bank(example_path)
        assert bank["meta"]["candidate_name"] == "Alex Sample"


# ---------------------------------------------------------------------------
# Missing top-level sections
# ---------------------------------------------------------------------------

class TestMissingSections:
    def test_missing_meta(self, valid_bank):
        del valid_bank["meta"]
        errors = validate_resume_bank(valid_bank)
        assert any("meta" in e for e in errors)

    def test_missing_contact(self, valid_bank):
        del valid_bank["contact"]
        errors = validate_resume_bank(valid_bank)
        assert any("contact" in e for e in errors)

    def test_missing_skills(self, valid_bank):
        del valid_bank["skills"]
        errors = validate_resume_bank(valid_bank)
        assert any("skills" in e for e in errors)

    def test_missing_experience(self, valid_bank):
        valid_bank["experience"] = []
        errors = validate_resume_bank(valid_bank)
        assert any("experience" in e.lower() or "No experience" in e for e in errors)

    def test_missing_education(self, valid_bank):
        valid_bank["education"] = []
        errors = validate_resume_bank(valid_bank)
        assert any("education" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Meta validation
# ---------------------------------------------------------------------------

class TestMetaValidation:
    def test_missing_candidate_name(self, valid_bank):
        del valid_bank["meta"]["candidate_name"]
        errors = validate_resume_bank(valid_bank)
        assert any("candidate_name" in e for e in errors)

    def test_missing_version(self, valid_bank):
        del valid_bank["meta"]["version"]
        errors = validate_resume_bank(valid_bank)
        assert any("version" in e for e in errors)


# ---------------------------------------------------------------------------
# Summary validation
# ---------------------------------------------------------------------------

class TestSummaryValidation:
    def test_too_few_summaries(self, valid_bank):
        valid_bank["summaries"] = [valid_bank["summaries"][0]]
        errors = validate_resume_bank(valid_bank)
        assert any("at least 2" in e for e in errors)

    def test_too_many_summaries(self, valid_bank):
        valid_bank["summaries"] = [
            {**valid_bank["summaries"][0], "id": f"sum-{i}"}
            for i in range(6)
        ]
        errors = validate_resume_bank(valid_bank)
        assert any("Maximum 5" in e for e in errors)

    def test_summary_exceeds_350_chars(self, valid_bank):
        valid_bank["summaries"][0]["text"] = "x" * 351
        errors = validate_resume_bank(valid_bank)
        assert any("350 chars" in e for e in errors)

    def test_summary_at_350_chars_ok(self, valid_bank):
        valid_bank["summaries"][0]["text"] = "x" * 350
        errors = validate_resume_bank(valid_bank)
        assert not any("350 chars" in e for e in errors)

    def test_summary_missing_id(self, valid_bank):
        del valid_bank["summaries"][0]["id"]
        errors = validate_resume_bank(valid_bank)
        assert any("'id'" in e for e in errors)

    def test_summary_missing_text(self, valid_bank):
        del valid_bank["summaries"][0]["text"]
        errors = validate_resume_bank(valid_bank)
        assert any("'text'" in e for e in errors)

    def test_duplicate_summary_ids(self, valid_bank):
        valid_bank["summaries"][1]["id"] = valid_bank["summaries"][0]["id"]
        errors = validate_resume_bank(valid_bank)
        assert any("Duplicate summary" in e for e in errors)


# ---------------------------------------------------------------------------
# Experience / bullet validation
# ---------------------------------------------------------------------------

class TestExperienceValidation:
    def test_role_missing_role_id(self, valid_bank):
        del valid_bank["experience"][0]["role_id"]
        errors = validate_resume_bank(valid_bank)
        assert any("'role_id'" in e for e in errors)

    def test_include_always_needs_3_bullets(self, valid_bank):
        valid_bank["experience"][0]["include_always"] = True
        valid_bank["experience"][0]["bullets"] = valid_bank["experience"][0]["bullets"][:2]
        errors = validate_resume_bank(valid_bank)
        assert any("at least 3" in e for e in errors)

    def test_include_always_false_allows_few_bullets(self, valid_bank):
        valid_bank["experience"][0]["include_always"] = False
        valid_bank["experience"][0]["bullets"] = valid_bank["experience"][0]["bullets"][:1]
        errors = validate_resume_bank(valid_bank)
        assert not any("at least 3" in e for e in errors)

    def test_bullet_missing_id(self, valid_bank):
        del valid_bank["experience"][0]["bullets"][0]["id"]
        errors = validate_resume_bank(valid_bank)
        assert any("'id'" in e for e in errors)

    def test_bullet_missing_text(self, valid_bank):
        del valid_bank["experience"][0]["bullets"][0]["text"]
        errors = validate_resume_bank(valid_bank)
        assert any("'text'" in e for e in errors)

    def test_bullet_missing_tags(self, valid_bank):
        del valid_bank["experience"][0]["bullets"][0]["tags"]
        errors = validate_resume_bank(valid_bank)
        assert any("'tags'" in e for e in errors)

    def test_bullet_missing_priority(self, valid_bank):
        del valid_bank["experience"][0]["bullets"][0]["priority"]
        errors = validate_resume_bank(valid_bank)
        assert any("'priority'" in e for e in errors)

    def test_bullet_missing_has_metric(self, valid_bank):
        del valid_bank["experience"][0]["bullets"][0]["has_metric"]
        errors = validate_resume_bank(valid_bank)
        assert any("'has_metric'" in e for e in errors)

    def test_duplicate_bullet_ids(self, valid_bank):
        valid_bank["experience"][0]["bullets"][1]["id"] = \
            valid_bank["experience"][0]["bullets"][0]["id"]
        errors = validate_resume_bank(valid_bank)
        assert any("Duplicate bullet" in e for e in errors)


# ---------------------------------------------------------------------------
# Skills validation
# ---------------------------------------------------------------------------

class TestSkillsValidation:
    def test_missing_technical(self, valid_bank):
        del valid_bank["skills"]["technical"]
        errors = validate_resume_bank(valid_bank)
        assert any("technical" in e for e in errors)

    def test_missing_platform(self, valid_bank):
        del valid_bank["skills"]["platform"]
        errors = validate_resume_bank(valid_bank)
        assert any("platform" in e for e in errors)

    def test_skill_entry_missing_skill_name(self, valid_bank):
        del valid_bank["skills"]["technical"][0]["skill"]
        errors = validate_resume_bank(valid_bank)
        assert any("'skill'" in e for e in errors)

    def test_skill_entry_missing_tags(self, valid_bank):
        del valid_bank["skills"]["technical"][0]["tags"]
        errors = validate_resume_bank(valid_bank)
        assert any("'tags'" in e for e in errors)


# ---------------------------------------------------------------------------
# Education validation
# ---------------------------------------------------------------------------

class TestEducationValidation:
    def test_education_missing_school(self, valid_bank):
        del valid_bank["education"][0]["school"]
        errors = validate_resume_bank(valid_bank)
        assert any("'school'" in e for e in errors)

    def test_education_missing_degree(self, valid_bank):
        del valid_bank["education"][0]["degree"]
        errors = validate_resume_bank(valid_bank)
        assert any("'degree'" in e for e in errors)

    def test_duplicate_education_id(self, valid_bank):
        # Use same id as a bullet
        valid_bank["education"][0]["id"] = "b01"
        errors = validate_resume_bank(valid_bank)
        assert any("Duplicate education" in e for e in errors)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_get_all_bullet_ids(self, valid_bank):
        ids = get_all_bullet_ids(valid_bank)
        assert "b01" in ids
        assert "b02" in ids
        assert "b03" in ids
        assert "b04" in ids
        assert len(ids) == 4  # fixture has 4 bullets

    def test_get_all_bullet_ids_with_projects(self):
        example_path = Path(__file__).parent.parent / "examples" / "resume_bank.example.json"
        with open(example_path) as f:
            bank = json.load(f)
        ids = get_all_bullet_ids(bank)
        assert "pb01" in ids  # project bullet

    def test_get_role_bullet_ids(self, valid_bank):
        ids = get_role_bullet_ids(valid_bank, "role-ex1")
        assert ids == {"b01", "b02", "b03", "b04"}

    def test_get_role_bullet_ids_unknown_role(self, valid_bank):
        ids = get_role_bullet_ids(valid_bank, "role-nonexistent")
        assert ids == set()


# ---------------------------------------------------------------------------
# load_resume_bank error cases
# ---------------------------------------------------------------------------

class TestLoadErrors:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_resume_bank(tmp_path / "nonexistent.json")

    def test_invalid_bank_raises_value_error(self, tmp_path):
        bad_bank = {"meta": {}, "summaries": []}
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad_bank))
        with pytest.raises(ValueError, match="validation failed"):
            load_resume_bank(path)


# ---------------------------------------------------------------------------
# Multiple errors reported at once
# ---------------------------------------------------------------------------

class TestMultipleErrors:
    def test_reports_all_errors(self):
        """An almost-empty bank should report many errors at once."""
        bank = {}
        errors = validate_resume_bank(bank)
        assert len(errors) >= 5  # meta, contact, summaries, experience, skills, education
