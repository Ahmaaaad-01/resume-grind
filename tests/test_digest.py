"""Tests for src/digest.py and src/notifier.py."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.digest import _build_warnings, build_digest
from src.notifier import _build_subject_line, notify


# ---------------------------------------------------------------------------
# _build_warnings
# ---------------------------------------------------------------------------

class TestBuildWarnings:
    def test_no_warnings_clean_job(self):
        job = {"final_score": 75, "jd_source": "full_fetch", "jd_word_count": 500}
        assert _build_warnings(job) == []

    def test_short_jd_warning(self):
        job = {"jd_source": "serpapi_snippet", "jd_word_count": 80}
        warnings = _build_warnings(job)
        assert any("Short JD" in w for w in warnings)

    def test_no_short_jd_warning_for_full_fetch(self):
        job = {"jd_source": "full_fetch", "jd_word_count": 80}
        warnings = _build_warnings(job)
        assert not any("Short JD" in w for w in warnings)

    def test_experimental_title_warning(self):
        job = {"title_experimental": True}
        warnings = _build_warnings(job)
        assert any("Non-standard PM title" in w for w in warnings)

    def test_target_company_override_warning(self):
        job = {"target_company_override": True, "company": "Robinhood"}
        warnings = _build_warnings(job)
        assert any("Robinhood" in w and "relocation" in w.lower() for w in warnings)

    def test_validation_errors_as_warnings(self):
        job = {"validation_errors": ["INVALID source_id: b99"]}
        warnings = _build_warnings(job)
        assert any("b99" in w for w in warnings)

    def test_large_keyword_gap(self):
        job = {"keyword_stats": {"missing": ["a", "b", "c", "d", "e", "f"]}}
        warnings = _build_warnings(job)
        assert any("6 JD keywords" in w for w in warnings)

    def test_five_missing_no_warning(self):
        job = {"keyword_stats": {"missing": ["a", "b", "c", "d", "e"]}}
        warnings = _build_warnings(job)
        assert not any("keywords unmatched" in w for w in warnings)


# ---------------------------------------------------------------------------
# build_digest
# ---------------------------------------------------------------------------

class TestBuildDigest:
    def _make_results(self, **overrides):
        results = {
            "run_date": "2026-03-21",
            "top_matches": [],
            "worth_a_look": [],
            "resurfaced": [],
            "review_carefully": [],
            "stats": {
                "total_jobs": 10,
                "resumes_generated": 3,
                "hard_filter_passed": 8,
                "pass1_filtered": 2,
                "jd_full_fetch": 4,
                "jd_snippet": 3,
                "jd_skipped": 1,
                "nyc_jobs": 7,
                "remote_jobs": 3,
                "experimental_titles": 1,
                "target_overrides": 0,
                "errors": [],
            },
        }
        results.update(overrides)
        return results

    def test_renders_html(self):
        html = build_digest(self._make_results())
        assert "<html" in html
        assert "2026-03-21" in html

    def test_contains_stats(self):
        html = build_digest(self._make_results())
        assert "10" in html  # total_jobs
        assert "3" in html  # resumes_generated

    def test_top_match_appears(self):
        results = self._make_results(top_matches=[{
            "company": "TechCorp",
            "title_raw": "APM",
            "final_score": 85,
            "location": "NYC",
            "date_posted": "Today",
            "query_source": "nyc",
            "url": "https://example.com",
            "jd_source": "full_fetch",
            "jd_word_count": 500,
        }])
        html = build_digest(results)
        assert "TechCorp" in html
        assert "85" in html

    def test_worth_a_look_appears(self):
        results = self._make_results(worth_a_look=[{
            "company": "MidCo",
            "title_raw": "PM",
            "final_score": 52,
            "location": "NJ",
            "date_posted": "Yesterday",
            "query_source": "nyc",
            "url": "https://example.com",
        }])
        html = build_digest(results)
        assert "MidCo" in html
        assert "Worth a Look" in html

    def test_resurfaced_section(self):
        results = self._make_results(resurfaced=[{
            "company": "OldCo",
            "title_raw": "PM",
            "final_score": 65,
            "first_seen_run": "2026-03-14",
            "url": "",
        }])
        html = build_digest(results)
        assert "OldCo" in html
        assert "Still Open" in html

    def test_warned_jobs_move_to_review(self):
        results = self._make_results(top_matches=[{
            "company": "WarnCo",
            "title_raw": "PM",
            "final_score": 70,
            "location": "NYC",
            "date_posted": "Today",
            "query_source": "nyc",
            "url": "",
            "title_experimental": True,
            "jd_source": "full_fetch",
            "jd_word_count": 500,
        }])
        html = build_digest(results)
        # Should be in Review Carefully, not Top Matches
        assert "Review Carefully" in html
        assert "WarnCo" in html

    def test_footer_stats(self):
        html = build_digest(self._make_results())
        assert "Pass 1 filtered" in html
        assert "NYC queries" in html
        assert "Remote query" in html

    def test_experimental_title_stat_in_footer(self):
        html = build_digest(self._make_results())
        assert "Experimental title" in html

    def test_default_stats_filled(self):
        """Missing stats keys should be filled with defaults."""
        results = {"run_date": "2026-03-21", "stats": {}}
        html = build_digest(results)
        assert "<html" in html  # Should not crash


# ---------------------------------------------------------------------------
# _build_subject_line
# ---------------------------------------------------------------------------

class TestSubjectLine:
    def test_basic_subject(self):
        subject = _build_subject_line("2026-03-21", 10, 3)
        assert "Mar 21" in subject
        assert "10 roles" in subject
        assert "3 resumes" in subject


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------

class TestNotify:
    @patch("src.notifier.webbrowser.open")
    def test_saves_local_digest(self, mock_open, tmp_path):
        # Monkey-patch PROJECT_ROOT for test
        import src.notifier as notifier_mod
        original_root = notifier_mod.PROJECT_ROOT
        notifier_mod.PROJECT_ROOT = tmp_path

        try:
            html = "<html><body>Test digest</body></html>"
            config = {"notification": {"gmail_enabled": False}}
            path = notify(html, [], config, run_date="2026-03-21")

            assert path.exists()
            assert path.name == "2026-03-21.html"
            assert "Test digest" in path.read_text()
            mock_open.assert_called_once()
        finally:
            notifier_mod.PROJECT_ROOT = original_root

    @patch("src.notifier.webbrowser.open")
    def test_gmail_disabled_no_error(self, mock_open, tmp_path):
        import src.notifier as notifier_mod
        original_root = notifier_mod.PROJECT_ROOT
        notifier_mod.PROJECT_ROOT = tmp_path

        try:
            config = {"notification": {"gmail_enabled": False}}
            path = notify("<html></html>", [], config, run_date="2026-03-21")
            assert path.exists()
        finally:
            notifier_mod.PROJECT_ROOT = original_root

    @patch("src.notifier.webbrowser.open", side_effect=Exception("No browser"))
    def test_browser_failure_non_fatal(self, mock_open, tmp_path):
        import src.notifier as notifier_mod
        original_root = notifier_mod.PROJECT_ROOT
        notifier_mod.PROJECT_ROOT = tmp_path

        try:
            config = {"notification": {"gmail_enabled": False}}
            path = notify("<html></html>", [], config, run_date="2026-03-21")
            assert path.exists()  # Still saves even if browser fails
        finally:
            notifier_mod.PROJECT_ROOT = original_root
