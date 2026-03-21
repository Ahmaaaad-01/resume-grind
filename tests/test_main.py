"""Tests for src/main.py — pipeline orchestration."""

from unittest.mock import patch, MagicMock

import pytest

from src.main import _build_match_reason


class TestBuildMatchReason:
    def test_strong_title(self):
        result = {"title": 25, "company": 3, "location": 6}
        reason = _build_match_reason(result)
        assert "strong title match" in reason

    def test_target_company(self):
        result = {"title": 20, "company": 10, "location": 6}
        reason = _build_match_reason(result)
        assert "target company" in reason

    def test_tech_company(self):
        result = {"title": 20, "company": 6, "location": 6}
        reason = _build_match_reason(result)
        assert "tech/fintech" in reason

    def test_good_location(self):
        result = {"title": 20, "company": 3, "location": 10}
        reason = _build_match_reason(result)
        assert "good location" in reason

    def test_keyword_overlap(self):
        result = {"title": 20, "company": 3, "location": 6,
                  "keyword_match_count": 12}
        reason = _build_match_reason(result)
        assert "keyword overlap" in reason
        assert "12/20" in reason

    def test_general_match_fallback(self):
        result = {"title": 10, "company": 3, "location": 2}
        reason = _build_match_reason(result)
        assert reason == "general match"

    def test_empty_dict(self):
        assert _build_match_reason({}) == "general match"
