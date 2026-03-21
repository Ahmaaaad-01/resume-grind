"""Tests for src/jd_extractor.py — fallback chain, word count threshold, error handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.jd_extractor import extract_jd, fetch_and_parse, _count_words

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _count_words
# ---------------------------------------------------------------------------

class TestCountWords:
    def test_normal_text(self):
        assert _count_words("hello world foo bar") == 4

    def test_empty_string(self):
        assert _count_words("") == 0

    def test_multiline(self):
        assert _count_words("hello\nworld\nfoo") == 3


# ---------------------------------------------------------------------------
# extract_jd fallback chain
# ---------------------------------------------------------------------------

class TestExtractJd:
    """Test the full fallback chain: URL fetch → snippet → skip."""

    @patch("src.jd_extractor.fetch_and_parse")
    def test_full_fetch_success(self, mock_fetch):
        """When URL fetch returns enough words, use it."""
        long_text = " ".join(["word"] * 100)
        mock_fetch.return_value = long_text

        job = {"url": "https://example.com/job", "description_snippet": "short"}
        jd_text, source, word_count = extract_jd(job)

        assert source == "full_fetch"
        assert word_count == 100
        assert jd_text == long_text
        mock_fetch.assert_called_once_with("https://example.com/job")

    @patch("src.jd_extractor.fetch_and_parse")
    def test_full_fetch_too_short_falls_back_to_snippet(self, mock_fetch):
        """When URL fetch returns < 50 words, fall back to snippet."""
        mock_fetch.return_value = "only a few words here"
        snippet = " ".join(["word"] * 60)

        job = {"url": "https://example.com/job", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)

        assert source == "serpapi_snippet"
        assert word_count == 60

    @patch("src.jd_extractor.fetch_and_parse")
    def test_full_fetch_error_falls_back_to_snippet(self, mock_fetch):
        """When URL fetch throws, fall back to snippet."""
        mock_fetch.side_effect = Exception("Connection refused")
        snippet = " ".join(["word"] * 75)

        job = {"url": "https://example.com/job", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)

        assert source == "serpapi_snippet"
        assert word_count == 75

    def test_no_url_uses_snippet(self):
        """When no URL, go straight to snippet."""
        snippet = " ".join(["word"] * 55)
        job = {"url": "", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)

        assert source == "serpapi_snippet"
        assert word_count == 55

    def test_snippet_too_short_skips(self):
        """When snippet < 50 words, return skipped."""
        job = {"url": "", "description_snippet": "too short"}
        jd_text, source, word_count = extract_jd(job)

        assert source == "skipped"
        assert jd_text == ""
        assert word_count == 2

    def test_no_url_no_snippet_skips(self):
        """When no URL and no snippet, return skipped."""
        job = {"url": "", "description_snippet": ""}
        jd_text, source, word_count = extract_jd(job)

        assert source == "skipped"
        assert jd_text == ""

    @patch("src.jd_extractor.fetch_and_parse")
    def test_both_sources_too_short_skips(self, mock_fetch):
        """When both URL text and snippet are under threshold, skip."""
        mock_fetch.return_value = "tiny"
        job = {"url": "https://example.com", "description_snippet": "also tiny"}
        jd_text, source, word_count = extract_jd(job)

        assert source == "skipped"

    @patch("src.jd_extractor.fetch_and_parse")
    def test_custom_min_words(self, mock_fetch):
        """Custom min_words threshold is respected."""
        mock_fetch.return_value = " ".join(["word"] * 30)
        snippet = " ".join(["word"] * 30)

        job = {"url": "https://example.com", "description_snippet": snippet}

        # With default threshold (50), both sources are too short
        jd_text, source, _ = extract_jd(job, min_words=50)
        assert source == "skipped"

        # With lower threshold (20), full_fetch works
        jd_text, source, _ = extract_jd(job, min_words=20)
        assert source == "full_fetch"

    def test_missing_keys_no_crash(self):
        """Job dict missing url/description_snippet should not crash."""
        job = {}
        jd_text, source, word_count = extract_jd(job)
        assert source == "skipped"
        assert jd_text == ""

    @patch("src.jd_extractor.fetch_and_parse")
    def test_timeout_falls_back(self, mock_fetch):
        """Timeout on URL fetch falls back to snippet."""
        import httpx
        mock_fetch.side_effect = httpx.TimeoutException("timed out")
        snippet = " ".join(["word"] * 80)

        job = {"url": "https://slow-site.com/job", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)

        assert source == "serpapi_snippet"
        assert word_count == 80

    def test_none_snippet_treated_as_empty(self):
        """None description_snippet should be treated as empty string."""
        job = {"url": "", "description_snippet": None}
        jd_text, source, word_count = extract_jd(job)
        assert source == "skipped"


# ---------------------------------------------------------------------------
# Word count boundary tests
# ---------------------------------------------------------------------------

class TestWordCountBoundary:
    """Test the 50-word boundary precisely."""

    def test_exactly_50_words_passes(self):
        """Exactly 50 words should pass the threshold."""
        snippet = " ".join(["word"] * 50)
        job = {"url": "", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)
        assert source == "serpapi_snippet"
        assert word_count == 50

    def test_49_words_skips(self):
        """49 words should be skipped."""
        snippet = " ".join(["word"] * 49)
        job = {"url": "", "description_snippet": snippet}
        jd_text, source, word_count = extract_jd(job)
        assert source == "skipped"


# ---------------------------------------------------------------------------
# Integration test with real fixture
# ---------------------------------------------------------------------------

class TestWithFixture:
    """Test extract_jd with fixture data from discovery."""

    def test_serpapi_snippet_from_fixture_job(self):
        """A fixture job with long description should use serpapi_snippet when URL fetch is skipped."""
        job = {
            "url": "",  # No URL — go straight to snippet
            "description_snippet": (FIXTURES_DIR / "fake_jd.md").read_text(),
        }
        jd_text, source, word_count = extract_jd(job)
        assert source == "serpapi_snippet"
        assert word_count > 50
        assert "product management" in jd_text.lower() or "product manager" in jd_text.lower()
