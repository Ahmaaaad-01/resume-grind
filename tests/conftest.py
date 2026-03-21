"""Shared test fixtures."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_resume_bank():
    with open(FIXTURES_DIR / "fake_resume_bank.json") as f:
        return json.load(f)


@pytest.fixture
def fake_config():
    """A minimal config dict matching the spec's config.yaml structure."""
    return {
        "search": {
            "nyc_queries": [
                "associate product manager",
                "product manager entry level",
                "APM product",
                "junior product manager PM1",
                "product manager",
            ],
            "remote_queries": ["product manager remote"],
            "serpapi_location": "New York, NY",
            "remote_search_location": "United States",
            "date_filter": "3days",
            "results_per_query": 10,
        },
        "location": {
            "target_metro": "new_york",
            "metro_aliases": [
                "new york",
                "nyc",
                "manhattan",
                "brooklyn",
                "queens",
                "jersey city",
                "hoboken",
                "new york, ny",
                "ny metro",
            ],
            "accept_remote": True,
            "accept_hybrid_in_metro": True,
            "accept_onsite_in_metro": True,
            "accept_relocation": False,
        },
        "title_filter": {
            "experimental_allowlist": [
                r"\bproduct operations\b",
                r"\bgrowth analyst\b",
                r"\bproduct strategy\b",
            ],
        },
        "scoring": {
            "pass1_cutoff": 30,
            "core_skills": [
                "product management", "roadmap", "A/B testing", "user research",
                "agile", "scrum", "cross-functional", "stakeholder management",
                "SQL", "data analysis", "KPIs", "metrics", "mobile",
                "consumer", "fintech", "Jira", "Figma", "PRD",
                "user stories", "go-to-market",
            ],
            "target_companies": [
                "Robinhood", "Stripe", "Square", "Block", "Cash App",
                "Coinbase", "Chime", "SoFi", "Plaid", "Affirm",
                "Duolingo", "Spotify", "Notion", "Figma", "Discord",
                "DoorDash", "Instacart", "Airbnb", "Reddit", "Pinterest",
            ],
            "tech_fintech_signals": [
                "tech", "labs", "ai", "fintech", "software",
                "digital", "crypto", "blockchain", "payments", "neobank",
            ],
            "thresholds": {
                "generate_resume": 60,
                "include_in_digest": 40,
            },
        },
        "jd_extraction": {
            "min_word_count": 50,
            "short_jd_warning_threshold": 150,
        },
        "tailoring": {
            "max_derived_bullets": 3,
            "max_bullets_per_role": 4,
            "min_bullets_per_role": 3,
        },
        "output": {
            "resume_format": "docx",
            "file_naming": "{first}_{last}_Resume_{company}_{title}",
        },
        "notification": {
            "always_local_html": True,
            "gmail_enabled": False,
        },
    }
