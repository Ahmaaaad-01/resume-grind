"""Tests for src/discovery.py — SerpAPI response normalization, dedup, and dry-run."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.discovery import (
    _normalize_job,
    run_discovery,
    run_discovery_dry_run,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _normalize_job tests
# ---------------------------------------------------------------------------

class TestNormalizeJob:
    """Test normalization of SerpAPI job results into standard dicts."""

    def test_basic_normalization(self):
        raw = {
            "title": "Associate Product Manager",
            "company_name": "TechCorp",
            "location": "New York, NY",
            "description": "Some JD text here",
            "detected_extensions": {"posted_at": "Today", "schedule_type": "Full-time"},
            "apply_options": [{"title": "LinkedIn", "link": "https://linkedin.com/job/1"}],
            "job_id": "ABC123",
            "via": "LinkedIn",
            "share_link": "https://google.com/jobs/share/1",
        }
        job = _normalize_job(raw, "nyc")

        assert job["title_raw"] == "Associate Product Manager"
        assert job["company"] == "TechCorp"
        assert job["location"] == "New York, NY"
        assert job["url"] == "https://linkedin.com/job/1"
        assert job["date_posted"] == "Today"
        assert job["description_snippet"] == "Some JD text here"
        assert job["query_source"] == "nyc"
        assert job["job_id"] == "ABC123"
        assert job["via"] == "LinkedIn"
        assert isinstance(job["dedup_key"], str)
        assert len(job["dedup_key"]) == 16

    def test_remote_query_source(self):
        raw = {
            "title": "PM Remote",
            "company_name": "Co",
            "location": "United States",
            "description": "",
            "apply_options": [],
        }
        job = _normalize_job(raw, "remote")
        assert job["query_source"] == "remote"

    def test_fallback_to_share_link_when_no_apply_options(self):
        raw = {
            "title": "PM",
            "company_name": "Co",
            "location": "NYC",
            "description": "",
            "apply_options": [],
            "share_link": "https://google.com/jobs/share/123",
        }
        job = _normalize_job(raw, "nyc")
        assert job["url"] == "https://google.com/jobs/share/123"

    def test_no_url_at_all(self):
        raw = {
            "title": "PM",
            "company_name": "Co",
            "location": "NYC",
            "description": "",
        }
        job = _normalize_job(raw, "nyc")
        assert job["url"] == ""

    def test_missing_detected_extensions(self):
        raw = {
            "title": "PM",
            "company_name": "Co",
            "location": "NYC",
            "description": "",
        }
        job = _normalize_job(raw, "nyc")
        assert job["date_posted"] == ""

    def test_missing_fields_no_crash(self):
        """Sparse response should not crash — all fields have defaults."""
        raw = {}
        job = _normalize_job(raw, "nyc")
        assert job["title_raw"] == ""
        assert job["company"] == ""
        assert job["location"] == ""
        assert job["url"] == ""
        assert job["query_source"] == "nyc"

    def test_whitespace_stripping(self):
        raw = {
            "title": "  APM  ",
            "company_name": "  TechCorp  ",
            "location": "  NYC  ",
            "description": "desc",
        }
        job = _normalize_job(raw, "nyc")
        assert job["title_raw"] == "APM"
        assert job["company"] == "TechCorp"
        assert job["location"] == "NYC"

    def test_dedup_key_matches_db_module(self):
        """Verify dedup key is generated using db.make_dedup_key."""
        from src.db import make_dedup_key

        raw = {
            "title": "Associate Product Manager",
            "company_name": "TechCorp Inc.",
            "location": "New York, NY",
            "description": "",
        }
        job = _normalize_job(raw, "nyc")
        expected_key = make_dedup_key("TechCorp Inc.", "Associate Product Manager", "New York, NY")
        assert job["dedup_key"] == expected_key


# ---------------------------------------------------------------------------
# Dedup tests
# ---------------------------------------------------------------------------

class TestDedup:
    """Test that duplicate jobs across queries are deduplicated."""

    def test_dry_run_deduplicates(self):
        """Fixture has duplicate TechCorp APM — should dedup to 1."""
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        # Fixture has jobs 1 and 4 as dupes (same company/title/location)
        titles_companies = [(j["title_raw"], j["company"]) for j in jobs]
        techcorp_apms = [
            tc for tc in titles_companies
            if tc == ("Associate Product Manager", "TechCorp")
        ]
        assert len(techcorp_apms) == 1

    def test_dry_run_keeps_unique_jobs(self):
        """All non-duplicate jobs should be preserved."""
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        # Fixture has 7 jobs, 2 are dupes -> 6 unique
        assert len(jobs) == 6

    def test_first_occurrence_wins(self):
        """When deduping, the first occurrence (by query order) is kept."""
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        techcorp = next(j for j in jobs if j["company"] == "TechCorp")
        # First occurrence is via LinkedIn, not Glassdoor
        assert "linkedin" in techcorp["url"].lower()


# ---------------------------------------------------------------------------
# run_discovery tests (with mocked SerpAPI)
# ---------------------------------------------------------------------------

class TestRunDiscovery:
    """Test run_discovery with mocked SerpAPI calls."""

    def _make_config(self):
        return {
            "search": {
                "nyc_queries": ["product manager"],
                "remote_queries": ["product manager remote"],
                "serpapi_location": "New York, NY",
                "remote_search_location": "United States",
                "date_filter": "3days",
                "results_per_query": 10,
            }
        }

    @patch("src.discovery.GoogleSearch")
    @patch("src.discovery.get_env", return_value="fake-key")
    def test_tags_nyc_and_remote_sources(self, mock_env, MockSearch):
        """Jobs from NYC queries tagged 'nyc', remote queries tagged 'remote'."""
        nyc_result = {
            "jobs_results": [{
                "title": "PM NYC",
                "company_name": "NYC Co",
                "location": "New York, NY",
                "description": "NYC job",
                "apply_options": [],
            }]
        }
        remote_result = {
            "jobs_results": [{
                "title": "PM Remote",
                "company_name": "Remote Co",
                "location": "United States",
                "description": "Remote job",
                "apply_options": [],
            }]
        }

        mock_instance = MagicMock()
        mock_instance.get_dict.side_effect = [nyc_result, remote_result]
        MockSearch.return_value = mock_instance

        config = self._make_config()
        jobs = run_discovery(config)

        nyc_jobs = [j for j in jobs if j["query_source"] == "nyc"]
        remote_jobs = [j for j in jobs if j["query_source"] == "remote"]
        assert len(nyc_jobs) == 1
        assert len(remote_jobs) == 1
        assert nyc_jobs[0]["company"] == "NYC Co"
        assert remote_jobs[0]["company"] == "Remote Co"

    @patch("src.discovery.GoogleSearch")
    @patch("src.discovery.get_env", return_value="fake-key")
    def test_dedup_across_queries(self, mock_env, MockSearch):
        """Same job appearing in multiple queries is deduplicated."""
        shared_job = {
            "title": "Product Manager",
            "company_name": "SharedCo",
            "location": "New York, NY",
            "description": "Same job",
            "apply_options": [],
        }
        result = {"jobs_results": [shared_job]}

        mock_instance = MagicMock()
        mock_instance.get_dict.return_value = result
        MockSearch.return_value = mock_instance

        config = self._make_config()
        jobs = run_discovery(config)

        # Same job from both nyc and remote queries -> deduped to 1
        assert len(jobs) == 1

    @patch("src.discovery.GoogleSearch")
    @patch("src.discovery.get_env", return_value="fake-key")
    def test_handles_api_error_gracefully(self, mock_env, MockSearch):
        """If SerpAPI throws, that query returns empty but doesn't crash."""
        mock_instance = MagicMock()
        mock_instance.get_dict.side_effect = Exception("API error")
        MockSearch.return_value = mock_instance

        config = self._make_config()
        jobs = run_discovery(config)
        assert jobs == []

    @patch("src.discovery.GoogleSearch")
    @patch("src.discovery.get_env", return_value="fake-key")
    def test_handles_empty_results(self, mock_env, MockSearch):
        """Empty jobs_results from SerpAPI should return empty list."""
        mock_instance = MagicMock()
        mock_instance.get_dict.return_value = {"jobs_results": []}
        MockSearch.return_value = mock_instance

        config = self._make_config()
        jobs = run_discovery(config)
        assert jobs == []

    @patch("src.discovery.GoogleSearch")
    @patch("src.discovery.get_env", return_value="fake-key")
    def test_handles_missing_jobs_results_key(self, mock_env, MockSearch):
        """Response without jobs_results key should return empty list."""
        mock_instance = MagicMock()
        mock_instance.get_dict.return_value = {"search_metadata": {"status": "Success"}}
        MockSearch.return_value = mock_instance

        config = self._make_config()
        jobs = run_discovery(config)
        assert jobs == []


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------

class TestDryRun:
    """Test dry-run mode using fixture files."""

    def test_loads_from_fixture(self):
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        assert len(jobs) > 0

    def test_all_tagged_dry_run(self):
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        for job in jobs:
            assert job["query_source"] == "dry_run"

    def test_all_have_required_keys(self):
        jobs = run_discovery_dry_run(FIXTURES_DIR / "fake_serpapi_response.json")
        required_keys = {
            "title_raw", "company", "location", "url", "date_posted",
            "description_snippet", "query_source", "dedup_key",
        }
        for job in jobs:
            assert required_keys.issubset(job.keys()), f"Missing keys in job: {required_keys - job.keys()}"

    def test_default_fixture_path(self):
        """Default path should resolve to tests/fixtures/fake_serpapi_response.json."""
        jobs = run_discovery_dry_run()
        assert len(jobs) > 0
