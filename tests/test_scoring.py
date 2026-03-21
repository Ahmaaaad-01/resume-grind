"""Tests for src/scoring.py — two-pass scoring rubric."""

from datetime import date

import pytest

from src.scoring import (
    score_title,
    score_yoe,
    score_location,
    score_company,
    score_recency,
    score_keywords,
    score_pass1,
    passes_pass1_cutoff,
    score_pass2,
    classify_score,
)


# ===================================================================
# Title scoring (spec Section 3d)
# ===================================================================

class TestScoreTitle:

    # Early-career → 25 points
    def test_apm(self):
        assert score_title("APM") == 25

    def test_associate_product_manager(self):
        assert score_title("Associate Product Manager") == 25

    def test_pm1(self):
        assert score_title("PM1, Product Manager") == 25

    def test_pm_i(self):
        assert score_title("PM I") == 25

    def test_junior_product_manager(self):
        assert score_title("Junior Product Manager") == 25

    # Generic PM → 20 points
    def test_product_manager(self):
        assert score_title("Product Manager") == 20

    def test_product_manager_growth(self):
        assert score_title("Product Manager, Growth") == 20

    def test_product_manager_ii(self):
        assert score_title("Product Manager II") == 20

    # Specialty PM → 15 points
    def test_growth_pm(self):
        assert score_title("Growth PM") == 15

    def test_platform_pm(self):
        assert score_title("Platform PM") == 15

    def test_core_pm(self):
        assert score_title("Core PM") == 15

    def test_payments_pm(self):
        assert score_title("Payments PM") == 15

    # Product analyst → 12 points
    def test_product_analyst(self):
        assert score_title("Product Analyst") == 12

    # Other (passed hard filter) → 10 points
    def test_other_title(self):
        assert score_title("Product Operations") == 10

    # Case insensitivity
    def test_case_insensitive(self):
        assert score_title("ASSOCIATE PRODUCT MANAGER") == 25

    # APM takes priority over generic PM
    def test_apm_consumer(self):
        assert score_title("APM — Consumer") == 25


# ===================================================================
# YOE scoring (spec Section 3e)
# ===================================================================

class TestScoreYoe:

    def test_zero_to_two_years(self):
        assert score_yoe("1+ years of experience") == 20

    def test_two_years(self):
        assert score_yoe("2+ years of experience") == 20

    def test_three_years(self):
        assert score_yoe("3+ years of experience") == 18

    def test_one_to_three_range(self):
        assert score_yoe("1-3 years of experience") == 20

    def test_two_to_four_range(self):
        assert score_yoe("2-4 years of experience") == 20

    def test_three_to_five_range(self):
        assert score_yoe("3-5 years of experience") == 18

    def test_four_years(self):
        assert score_yoe("4+ years of experience") == 14

    def test_five_years(self):
        """5+ should have been hard-filtered, but if it gets here, scores 8."""
        assert score_yoe("5+ years of experience") == 8

    def test_not_specified(self):
        assert score_yoe("Great opportunity for product managers") == 12

    def test_empty(self):
        assert score_yoe("") == 12


# ===================================================================
# Location scoring (spec Section 3f)
# ===================================================================

class TestScoreLocation:

    def test_remote(self, fake_config):
        assert score_location("Remote", fake_config) == 10

    def test_work_from_home(self, fake_config):
        assert score_location("Work From Home", fake_config) == 10

    def test_anywhere(self, fake_config):
        assert score_location("Anywhere in US", fake_config) == 10

    def test_hybrid_in_metro(self, fake_config):
        assert score_location("Hybrid - New York, NY", fake_config) == 8

    def test_onsite_in_metro(self, fake_config):
        assert score_location("New York, NY", fake_config) == 6

    def test_manhattan(self, fake_config):
        assert score_location("Manhattan, NY", fake_config) == 6

    def test_outside_metro(self, fake_config):
        assert score_location("San Francisco, CA", fake_config) == 2

    def test_hybrid_outside_metro(self, fake_config):
        assert score_location("Hybrid - Chicago, IL", fake_config) == 2

    def test_unknown_location(self, fake_config):
        assert score_location("", fake_config) == 2


# ===================================================================
# Company scoring (spec Section 3h)
# ===================================================================

class TestScoreCompany:

    # Target list → 10
    def test_robinhood(self, fake_config):
        assert score_company("Robinhood", fake_config) == 10

    def test_stripe(self, fake_config):
        assert score_company("Stripe", fake_config) == 10

    def test_target_case_insensitive(self, fake_config):
        assert score_company("robinhood", fake_config) == 10

    def test_duolingo(self, fake_config):
        assert score_company("Duolingo", fake_config) == 10

    # Tech/fintech signal → 6
    def test_tech_signal(self, fake_config):
        assert score_company("Acme Tech", fake_config) == 6

    def test_fintech_signal(self, fake_config):
        assert score_company("Novo Fintech", fake_config) == 6

    def test_labs_signal(self, fake_config):
        assert score_company("DataViz Labs", fake_config) == 6

    def test_ai_signal(self, fake_config):
        assert score_company("Cerebral AI", fake_config) == 6

    def test_software_signal(self, fake_config):
        assert score_company("Ramp Software", fake_config) == 6

    def test_crypto_signal(self, fake_config):
        assert score_company("Nova Crypto", fake_config) == 6

    def test_payments_signal(self, fake_config):
        assert score_company("Global Payments", fake_config) == 6

    # Other → 3
    def test_other_company(self, fake_config):
        assert score_company("Acme Corp", fake_config) == 3

    def test_unknown_company(self, fake_config):
        assert score_company("Walmart", fake_config) == 3

    def test_empty_company(self, fake_config):
        assert score_company("", fake_config) == 3


# ===================================================================
# Recency scoring (spec Section 3i)
# ===================================================================

class TestScoreRecency:

    def test_today(self):
        assert score_recency("2026-03-21", today=date(2026, 3, 21)) == 10

    def test_yesterday(self):
        assert score_recency("2026-03-20", today=date(2026, 3, 21)) == 7

    def test_two_days_ago(self):
        assert score_recency("2026-03-19", today=date(2026, 3, 21)) == 4

    def test_three_days_ago(self):
        assert score_recency("2026-03-18", today=date(2026, 3, 21)) == 2

    def test_four_days_ago(self):
        assert score_recency("2026-03-17", today=date(2026, 3, 21)) == 2

    def test_no_date(self):
        assert score_recency(None) == 2

    def test_empty_date(self):
        assert score_recency("") == 2

    def test_unparseable_date(self):
        assert score_recency("not-a-date") == 2

    def test_future_date(self):
        """A future-dated post (clock skew) should get max points."""
        assert score_recency("2026-03-22", today=date(2026, 3, 21)) == 10


# ===================================================================
# Keyword overlap scoring (spec Section 3g)
# ===================================================================

class TestScoreKeywords:

    def test_full_match(self, fake_config):
        jd = (
            "product management roadmap A/B testing user research agile scrum "
            "cross-functional stakeholder management SQL data analysis KPIs "
            "metrics mobile consumer fintech Jira Figma PRD user stories go-to-market"
        )
        score, count, matched = score_keywords(jd, fake_config)
        assert count == 20
        assert score == 25

    def test_no_match(self, fake_config):
        jd = "We are looking for someone to join our team."
        score, count, matched = score_keywords(jd, fake_config)
        assert count == 0
        assert score == 0

    def test_partial_match(self, fake_config):
        jd = "Experience with SQL, agile methodologies, and user research required."
        score, count, matched = score_keywords(jd, fake_config)
        assert count == 3
        assert "SQL" in matched
        assert "agile" in matched
        assert "user research" in matched
        assert score == round((3 / 20) * 25)

    def test_case_insensitive(self, fake_config):
        jd = "PRODUCT MANAGEMENT and SQL skills required."
        score, count, matched = score_keywords(jd, fake_config)
        assert count >= 2

    def test_half_match(self, fake_config):
        jd = (
            "product management roadmap A/B testing user research agile "
            "scrum cross-functional stakeholder management SQL data analysis"
        )
        score, count, matched = score_keywords(jd, fake_config)
        assert count == 10
        assert score == round((10 / 20) * 25)  # 12 or 13

    def test_returns_matched_list(self, fake_config):
        jd = "We use Jira and Figma for product management."
        score, count, matched = score_keywords(jd, fake_config)
        assert "Jira" in matched
        assert "Figma" in matched
        assert "product management" in matched

    def test_empty_jd(self, fake_config):
        score, count, matched = score_keywords("", fake_config)
        assert count == 0
        assert score == 0


# ===================================================================
# Pass 1 scoring
# ===================================================================

class TestScorePass1:

    def test_strong_job(self, fake_config):
        job = {
            "title": "Associate Product Manager",
            "company": "Robinhood",
            "location": "Remote",
            "description": "1+ years of experience in product management",
            "date_posted": "2026-03-21",
        }
        result = score_pass1(job, fake_config, today=date(2026, 3, 21))
        assert result['title'] == 25
        assert result['company'] == 10
        assert result['location'] == 10
        assert result['recency'] == 10
        assert result['pass1_total'] == 25 + 20 + 10 + 10 + 10  # 75

    def test_weak_job(self, fake_config):
        job = {
            "title": "Product Analyst",
            "company": "Acme Corp",
            "location": "Chicago, IL",
            "description": "",
            "date_posted": "2026-03-18",
        }
        result = score_pass1(job, fake_config, today=date(2026, 3, 21))
        assert result['title'] == 12
        assert result['company'] == 3
        assert result['location'] == 2
        assert result['yoe'] == 12  # Not specified
        assert result['recency'] == 2
        assert result['pass1_total'] == 12 + 12 + 2 + 3 + 2  # 31

    def test_all_fields_present(self, fake_config):
        job = {
            "title": "Product Manager",
            "company": "Unknown",
            "location": "New York, NY",
            "description": "",
            "date_posted": "2026-03-21",
        }
        result = score_pass1(job, fake_config, today=date(2026, 3, 21))
        assert set(result.keys()) == {
            'title', 'yoe', 'location', 'company', 'recency', 'pass1_total'
        }


class TestPassesPass1Cutoff:

    def test_above_cutoff(self, fake_config):
        assert passes_pass1_cutoff(30, fake_config) is True

    def test_at_cutoff(self, fake_config):
        assert passes_pass1_cutoff(30, fake_config) is True

    def test_below_cutoff(self, fake_config):
        assert passes_pass1_cutoff(29, fake_config) is False

    def test_zero(self, fake_config):
        assert passes_pass1_cutoff(0, fake_config) is False

    def test_max(self, fake_config):
        assert passes_pass1_cutoff(75, fake_config) is True

    def test_custom_cutoff(self):
        config = {"scoring": {"pass1_cutoff": 20}}
        assert passes_pass1_cutoff(20, config) is True
        assert passes_pass1_cutoff(19, config) is False


# ===================================================================
# Pass 2 scoring
# ===================================================================

class TestScorePass2:

    def test_adds_keyword_score(self, fake_config):
        pass1 = {
            'title': 25,
            'yoe': 20,
            'location': 10,
            'company': 10,
            'recency': 10,
            'pass1_total': 75,
        }
        jd = "product management roadmap A/B testing user research agile"
        result = score_pass2(pass1, jd, fake_config)

        assert result['keywords'] > 0
        assert result['final_score'] == 75 + result['keywords']
        assert 'keyword_match_count' in result
        assert 'keyword_matched_skills' in result

    def test_preserves_pass1_fields(self, fake_config):
        pass1 = {
            'title': 20,
            'yoe': 12,
            'location': 6,
            'company': 3,
            'recency': 7,
            'pass1_total': 48,
        }
        result = score_pass2(pass1, "no skills here", fake_config)

        # All pass1 fields preserved
        assert result['title'] == 20
        assert result['yoe'] == 12
        assert result['location'] == 6
        assert result['company'] == 3
        assert result['recency'] == 7
        assert result['pass1_total'] == 48

    def test_no_keyword_overlap(self, fake_config):
        pass1 = {'title': 20, 'yoe': 12, 'location': 6, 'company': 3, 'recency': 7, 'pass1_total': 48}
        result = score_pass2(pass1, "We sell widgets.", fake_config)
        assert result['keywords'] == 0
        assert result['final_score'] == 48

    def test_perfect_score(self, fake_config):
        pass1 = {'title': 25, 'yoe': 20, 'location': 10, 'company': 10, 'recency': 10, 'pass1_total': 75}
        jd = (
            "product management roadmap A/B testing user research agile scrum "
            "cross-functional stakeholder management SQL data analysis KPIs "
            "metrics mobile consumer fintech Jira Figma PRD user stories go-to-market"
        )
        result = score_pass2(pass1, jd, fake_config)
        assert result['final_score'] == 100


# ===================================================================
# Score classification
# ===================================================================

class TestClassifyScore:

    def test_generate_resume(self, fake_config):
        assert classify_score(60, fake_config) == 'generate_resume'
        assert classify_score(75, fake_config) == 'generate_resume'
        assert classify_score(100, fake_config) == 'generate_resume'

    def test_include_in_digest(self, fake_config):
        assert classify_score(40, fake_config) == 'include_in_digest'
        assert classify_score(50, fake_config) == 'include_in_digest'
        assert classify_score(59, fake_config) == 'include_in_digest'

    def test_discard(self, fake_config):
        assert classify_score(39, fake_config) == 'discard'
        assert classify_score(0, fake_config) == 'discard'
        assert classify_score(10, fake_config) == 'discard'

    def test_boundary_60(self, fake_config):
        assert classify_score(60, fake_config) == 'generate_resume'
        assert classify_score(59, fake_config) == 'include_in_digest'

    def test_boundary_40(self, fake_config):
        assert classify_score(40, fake_config) == 'include_in_digest'
        assert classify_score(39, fake_config) == 'discard'
