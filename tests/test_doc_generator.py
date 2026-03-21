"""Tests for src/doc_generator.py — DOCX resume generation."""

import json
from pathlib import Path

import pytest
from docx import Document

from src.doc_generator import (
    _format_date_range,
    _sanitize_filename,
    generate_docx,
    generate_resume_filename,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bank():
    with open(FIXTURES_DIR / "fake_resume_bank.json") as f:
        return json.load(f)


@pytest.fixture
def tailored():
    return {
        "summary_used": "sum-consumer",
        "summary_text_final": "Product Manager with 2 years of experience building consumer mobile products.",
        "experience": [
            {
                "role_id": "role-ex1",
                "bullets_selected": [
                    {
                        "source_ids": ["b01"],
                        "tier": "rewritten",
                        "text_final": "Led development of a mobile checkout feature used by 500K+ monthly users",
                        "derivation_rationale": None,
                        "modification": "reframed",
                        "jd_relevance": 9,
                    },
                    {
                        "source_ids": ["b02"],
                        "tier": "rewritten",
                        "text_final": "Designed and ran A/B experiments on onboarding flow, improving 7-day retention by 12%",
                        "derivation_rationale": None,
                        "modification": "reframed",
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
        "skills_order": ["SQL", "A/B Testing", "Consumer Products", "Agile / Scrum"],
        "project_included": None,
        "gaps": ["No fintech experience"],
    }


@pytest.fixture
def job():
    return {
        "title_raw": "Associate Product Manager",
        "company": "TechCorp",
        "location": "New York, NY",
    }


# ---------------------------------------------------------------------------
# generate_docx — integration tests
# ---------------------------------------------------------------------------

class TestGenerateDocx:
    def test_creates_docx_file(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        assert path.exists()
        assert path.suffix == ".docx"

    def test_filename_format(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        assert "Alex" in path.name
        assert "Sample" in path.name
        assert "TechCorp" in path.name
        assert path.name.endswith(".docx")

    def test_docx_is_valid(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        assert len(doc.paragraphs) > 0

    def test_contains_candidate_name(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Alex Sample" in text

    def test_contains_contact_info(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "alex.sample@example.com" in text
        assert "555-000-0000" in text

    def test_contains_summary(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "consumer mobile products" in text

    def test_contains_bullet_text(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "500K+" in text
        assert "A/B experiments" in text

    def test_contains_company_name(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "Example Corp" in text

    def test_contains_skills(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "SQL" in text

    def test_contains_education(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "State University" in text
        assert "Business Administration" in text

    def test_contains_section_headers(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "SUMMARY" in text
        assert "EXPERIENCE" in text
        assert "SKILLS" in text
        assert "EDUCATION" in text

    def test_no_projects_section_when_none(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "PROJECTS" not in text

    def test_margins_set(self, bank, tailored, job, tmp_path):
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        from docx.shared import Inches
        for section in doc.sections:
            assert section.left_margin == Inches(0.7)
            assert section.right_margin == Inches(0.7)
            assert section.top_margin == Inches(0.7)
            assert section.bottom_margin == Inches(0.7)

    def test_creates_output_dir(self, bank, tailored, job, tmp_path):
        nested = tmp_path / "sub" / "dir"
        path = generate_docx(tailored, bank, job, output_dir=nested)
        assert path.exists()
        assert nested.exists()


# ---------------------------------------------------------------------------
# Project inclusion
# ---------------------------------------------------------------------------

class TestProjectInclusion:
    def test_project_included(self, bank, tailored, job, tmp_path):
        # Use the example bank which has a project
        example_path = Path(__file__).parent.parent / "examples" / "resume_bank.example.json"
        with open(example_path) as f:
            bank_with_proj = json.load(f)

        tailored["project_included"] = "proj-1"
        path = generate_docx(tailored, bank_with_proj, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "PROJECTS" in text
        assert "ShopTrack" in text


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestFormatDateRange:
    def test_normal_range(self):
        assert _format_date_range("2024-01", "2024-12") == "Jan 2024 – Dec 2024"

    def test_present(self):
        result = _format_date_range("2023-09", "present")
        assert "Sep 2023" in result
        assert "Present" in result

    def test_empty_dates(self):
        result = _format_date_range("", "")
        assert "–" in result


class TestSanitizeFilename:
    def test_removes_special_chars(self):
        assert _sanitize_filename("Hello/World!") == "HelloWorld"

    def test_replaces_spaces(self):
        assert _sanitize_filename("Hello World") == "Hello_World"

    def test_keeps_hyphens(self):
        assert _sanitize_filename("J.P. Morgan") == "JP_Morgan"


class TestGenerateResumeFilename:
    def test_basic_filename(self):
        bank = {"contact": {"name": "Alex Sample"}}
        job = {"company": "TechCorp", "title_raw": "APM"}
        name = generate_resume_filename(bank, job)
        assert name == "Alex_Sample_Resume_TechCorp_APM.docx"

    def test_long_title_truncated(self):
        bank = {"contact": {"name": "Alex Sample"}}
        job = {"company": "Co", "title_raw": "A" * 50}
        name = generate_resume_filename(bank, job)
        assert len(name) < 100

    def test_special_chars_in_company(self):
        bank = {"contact": {"name": "Alex Sample"}}
        job = {"company": "J.P. Morgan & Co.", "title_raw": "PM"}
        name = generate_resume_filename(bank, job)
        assert "/" not in name
        assert "&" not in name


# ---------------------------------------------------------------------------
# Skills renaming (new format)
# ---------------------------------------------------------------------------

class TestSkillsRenaming:
    def test_renamed_skills_in_docx(self, bank, tailored, job, tmp_path):
        """New-format skills_order with display names renders renamed skills."""
        tailored["skills_order"] = [
            {"original": "SQL", "display": "SQL & Data Analysis"},
            {"original": "Agile / Scrum", "display": "Agile Methodology"},
        ]
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "SQL & Data Analysis" in text
        assert "Agile Methodology" in text

    def test_old_format_skills_still_work(self, bank, tailored, job, tmp_path):
        """Old-format skills_order (list of strings) still works."""
        tailored["skills_order"] = ["SQL", "A/B Testing"]
        path = generate_docx(tailored, bank, job, output_dir=tmp_path, skip_pdf_check=True)
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "SQL" in text


# ---------------------------------------------------------------------------
# JD-aware trimming
# ---------------------------------------------------------------------------

class TestJdAwareTrimming:
    def test_lowest_relevance_trimmed_first(self, tmp_path):
        """When trimming, the lowest jd_relevance bullet is removed first."""
        from src.doc_generator import _build_doc, _trim_one_bullet, _build_relevance_map

        bank_data = {
            "contact": {"name": "Test"},
            "skills": {},
            "education": [],
            "experience": [
                {"role_id": "r1", "company": "Co", "title": "PM",
                 "start_date": "2024-01", "end_date": "present",
                 "location": "NYC", "include_always": True, "bullets": []},
            ],
            "summaries": [],
        }
        tailored_data = {
            "summary_text_final": "Summary.",
            "experience": [
                {
                    "role_id": "r1",
                    "bullets_selected": [
                        {"source_ids": ["x"], "tier": "rewritten",
                         "text_final": "High relevance bullet", "jd_relevance": 10,
                         "derivation_rationale": None, "modification": "reframed"},
                        {"source_ids": ["y"], "tier": "rewritten",
                         "text_final": "Low relevance bullet", "jd_relevance": 2,
                         "derivation_rationale": None, "modification": "reframed"},
                        {"source_ids": ["z"], "tier": "rewritten",
                         "text_final": "Mid relevance bullet", "jd_relevance": 6,
                         "derivation_rationale": None, "modification": "reframed"},
                    ],
                }
            ],
            "skills_order": [],
        }
        doc = _build_doc(tailored_data, bank_data)
        relevance_map = _build_relevance_map(tailored_data)
        removed = _trim_one_bullet(doc, relevance_map)
        assert removed is True
        # The low-relevance bullet should be gone
        remaining = [p.text for p in doc.paragraphs if p.text.startswith("• ")]
        assert "• Low relevance bullet" not in remaining
        assert "• High relevance bullet" in remaining
        assert "• Mid relevance bullet" in remaining
