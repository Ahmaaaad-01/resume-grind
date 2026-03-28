"""Tests for src/filtering.py — hard filters, title classification, location, YOE."""

import pytest

from src.filtering import (
    classify_title,
    normalize_title,
    passes_location_filter,
    is_target_company_override,
    extract_yoe,
    check_yoe,
    passes_hard_filters,
)


# ===================================================================
# Title classification — spec edge-case table (Section 2a)
# ===================================================================

class TestClassifyTitle:
    """Every row from the spec's edge-case table."""

    # --- Core PM titles that SHOULD pass ---

    def test_product_manager(self, fake_config):
        passes, norm, exp = classify_title("Product Manager", fake_config)
        assert passes is True
        assert exp is False

    def test_associate_product_manager(self, fake_config):
        passes, norm, exp = classify_title("Associate Product Manager", fake_config)
        assert passes is True
        assert exp is False

    def test_pm1_product_manager(self, fake_config):
        passes, norm, exp = classify_title("PM1, Product Manager", fake_config)
        assert passes is True
        assert exp is False

    def test_product_manager_growth(self, fake_config):
        passes, norm, exp = classify_title("Product Manager, Growth", fake_config)
        assert passes is True
        assert exp is False

    def test_product_manager_ii(self, fake_config):
        passes, norm, exp = classify_title("Product Manager II", fake_config)
        assert passes is True
        assert exp is False

    def test_junior_product_manager(self, fake_config):
        passes, norm, exp = classify_title("Junior Product Manager", fake_config)
        assert passes is True
        assert exp is False

    def test_apm_consumer(self, fake_config):
        passes, norm, exp = classify_title("APM — Consumer", fake_config)
        assert passes is True
        assert exp is False

    def test_product_analyst(self, fake_config):
        passes, norm, exp = classify_title("Product Analyst", fake_config)
        assert passes is True
        assert exp is False

    def test_product_management_intern(self, fake_config):
        passes, norm, exp = classify_title("Product Management Intern", fake_config)
        assert passes is True
        assert exp is False

    # --- Seniority rejects ---

    def test_senior_product_manager(self, fake_config):
        passes, _, _ = classify_title("Senior Product Manager", fake_config)
        assert passes is False

    def test_sr_product_manager_payments(self, fake_config):
        passes, _, _ = classify_title("Sr. Product Manager, Payments", fake_config)
        assert passes is False

    def test_lead_product_manager(self, fake_config):
        passes, _, _ = classify_title("Lead Product Manager", fake_config)
        assert passes is False

    def test_group_product_manager(self, fake_config):
        passes, _, _ = classify_title("Group Product Manager", fake_config)
        assert passes is False

    def test_staff_product_manager(self, fake_config):
        passes, _, _ = classify_title("Staff Product Manager", fake_config)
        assert passes is False

    def test_director_of_product(self, fake_config):
        passes, _, _ = classify_title("Director of Product", fake_config)
        assert passes is False

    def test_vp_product(self, fake_config):
        passes, _, _ = classify_title("VP Product", fake_config)
        assert passes is False

    # --- Wrong "PM" roles ---

    def test_project_manager(self, fake_config):
        passes, _, _ = classify_title("Project Manager", fake_config)
        assert passes is False

    def test_technical_program_manager(self, fake_config):
        passes, _, _ = classify_title("Technical Program Manager", fake_config)
        assert passes is False

    def test_program_manager_operations(self, fake_config):
        passes, _, _ = classify_title("Program Manager, Operations", fake_config)
        assert passes is False

    def test_property_manager(self, fake_config):
        passes, _, _ = classify_title("Property Manager", fake_config)
        assert passes is False

    # --- Time-based "PM" ---

    def test_pm_shift_lead(self, fake_config):
        passes, _, _ = classify_title("PM Shift Lead — Retail", fake_config)
        assert passes is False

    # --- Adjacent but wrong roles ---

    def test_marketing_manager(self, fake_config):
        passes, _, _ = classify_title("Marketing Manager", fake_config)
        assert passes is False

    def test_performance_marketing_pm(self, fake_config):
        passes, _, _ = classify_title("Performance Marketing PM", fake_config)
        assert passes is False

    def test_engineering_manager(self, fake_config):
        passes, _, _ = classify_title("Engineering Manager", fake_config)
        assert passes is False

    def test_tpm_cloud(self, fake_config):
        passes, _, _ = classify_title("TPM — Cloud Infrastructure", fake_config)
        assert passes is False

    # --- Standalone "PM" (no context) — reject ---

    def test_standalone_pm(self, fake_config):
        passes, _, _ = classify_title("PM", fake_config)
        assert passes is False

    # --- Dual titles — denylist catches "project manager" ---

    def test_dual_title_pm_project_manager(self, fake_config):
        passes, _, _ = classify_title("Product Manager / Project Manager", fake_config)
        assert passes is False

    # --- Experimental allowlist ---

    def test_product_operations_experimental(self, fake_config):
        passes, norm, exp = classify_title("Product Operations", fake_config)
        assert passes is True
        assert exp is True

    def test_growth_analyst_experimental(self, fake_config):
        passes, norm, exp = classify_title("Growth Analyst", fake_config)
        assert passes is True
        assert exp is True

    def test_product_strategy_experimental(self, fake_config):
        passes, norm, exp = classify_title("Product Strategy", fake_config)
        assert passes is True
        assert exp is True

    # --- Experimental allowlist disabled (empty config) ---

    def test_product_operations_no_experimental(self):
        config = {"title_filter": {"experimental_allowlist": []}}
        passes, _, _ = classify_title("Product Operations", config)
        assert passes is False

    # --- Case insensitivity ---

    def test_case_insensitive_pass(self, fake_config):
        passes, _, _ = classify_title("PRODUCT MANAGER", fake_config)
        assert passes is True

    def test_case_insensitive_reject(self, fake_config):
        passes, _, _ = classify_title("SENIOR PRODUCT MANAGER", fake_config)
        assert passes is False


# ===================================================================
# Title normalization
# ===================================================================

class TestNormalizeTitle:

    def test_strips_junior_prefix(self):
        assert normalize_title("Junior Product Manager") == "product manager"

    def test_strips_associate_prefix(self):
        assert normalize_title("Associate Product Manager") == "product manager"

    def test_strips_remote_suffix(self):
        assert normalize_title("Product Manager - Remote") == "product manager"

    def test_strips_hybrid_suffix(self):
        assert normalize_title("Product Manager, Hybrid") == "product manager"

    def test_strips_parenthetical(self):
        assert normalize_title("Product Manager (Remote)") == "product manager"

    def test_normalizes_apm(self):
        assert normalize_title("APM") == "product manager"

    def test_normalizes_pm1(self):
        assert normalize_title("PM1") == "product manager 1"

    def test_normalizes_pm_i(self):
        assert normalize_title("PM I") == "product manager i"

    def test_normalizes_pm_ii(self):
        assert normalize_title("PM II") == "product manager ii"

    def test_preserves_growth_qualifier(self):
        assert normalize_title("Product Manager, Growth") == "product manager, growth"

    def test_collapses_whitespace(self):
        assert normalize_title("  Product   Manager  ") == "product manager"

    def test_entry_level_prefix(self):
        assert normalize_title("Entry Level Product Manager") == "product manager"

    def test_entry_level_hyphenated(self):
        assert normalize_title("Entry-Level Product Manager") == "product manager"


# ===================================================================
# Location filter
# ===================================================================

class TestLocationFilter:

    def test_remote_passes(self, fake_config):
        assert passes_location_filter("Remote", "Unknown Corp", fake_config) is True

    def test_work_from_home_passes(self, fake_config):
        assert passes_location_filter("Work From Home", "Unknown Corp", fake_config) is True

    def test_anywhere_passes(self, fake_config):
        assert passes_location_filter("Anywhere in US", "Unknown Corp", fake_config) is True

    def test_distributed_passes(self, fake_config):
        assert passes_location_filter("Distributed", "Unknown Corp", fake_config) is True

    def test_nyc_passes(self, fake_config):
        assert passes_location_filter("New York, NY", "Unknown Corp", fake_config) is True

    def test_manhattan_passes(self, fake_config):
        assert passes_location_filter("Manhattan, NY", "Unknown Corp", fake_config) is True

    def test_brooklyn_passes(self, fake_config):
        assert passes_location_filter("Brooklyn, NY", "Unknown Corp", fake_config) is True

    def test_jersey_city_passes(self, fake_config):
        assert passes_location_filter("Jersey City, NJ", "Unknown Corp", fake_config) is True

    def test_hoboken_passes(self, fake_config):
        assert passes_location_filter("Hoboken, NJ", "Unknown Corp", fake_config) is True

    def test_hybrid_in_metro_passes(self, fake_config):
        assert passes_location_filter("Hybrid - New York, NY", "Unknown Corp", fake_config) is True

    def test_hybrid_outside_metro_rejects(self, fake_config):
        assert passes_location_filter("Hybrid - Chicago, IL", "Unknown Corp", fake_config) is False

    def test_onsite_outside_metro_rejects(self, fake_config):
        assert passes_location_filter("San Francisco, CA", "Unknown Corp", fake_config) is False

    def test_chicago_rejects(self, fake_config):
        assert passes_location_filter("Chicago, IL", "Unknown Corp", fake_config) is False

    def test_austin_rejects(self, fake_config):
        assert passes_location_filter("Austin, TX", "Unknown Corp", fake_config) is False

    # --- Target-company override ---

    def test_target_company_sf_passes(self, fake_config):
        """Target company in SF should pass even though SF is not in metro."""
        assert passes_location_filter("San Francisco, CA", "Stripe", fake_config) is True

    def test_target_company_seattle_passes(self, fake_config):
        assert passes_location_filter("Seattle, WA", "Coinbase", fake_config) is True

    def test_target_company_case_insensitive(self, fake_config):
        assert passes_location_filter("Austin, TX", "robinhood", fake_config) is True

    def test_non_target_company_sf_rejects(self, fake_config):
        assert passes_location_filter("San Francisco, CA", "Random Inc", fake_config) is False

    # --- accept_relocation off ---

    def test_relocation_rejected_when_disabled(self, fake_config):
        assert fake_config["location"]["accept_relocation"] is False
        assert passes_location_filter("Denver, CO", "Unknown Corp", fake_config) is False

    # --- accept_relocation on ---

    def test_relocation_passes_when_enabled(self, fake_config):
        config = {**fake_config, "location": {**fake_config["location"], "accept_relocation": True}}
        assert passes_location_filter("Denver, CO", "Unknown Corp", config) is True


class TestTargetCompanyOverride:

    def test_target_company_in_sf_is_override(self, fake_config):
        """Stripe in SF passes ONLY because of override."""
        assert is_target_company_override("San Francisco, CA", "Stripe", fake_config) is True

    def test_target_company_in_nyc_not_override(self, fake_config):
        """Stripe in NYC would pass anyway — not an override."""
        assert is_target_company_override("New York, NY", "Stripe", fake_config) is False

    def test_target_company_remote_not_override(self, fake_config):
        """Target company remote would pass anyway."""
        assert is_target_company_override("Remote", "Robinhood", fake_config) is False

    def test_non_target_company_is_never_override(self, fake_config):
        assert is_target_company_override("San Francisco, CA", "Random Inc", fake_config) is False


# ===================================================================
# YOE extraction and filter
# ===================================================================

class TestExtractYoe:

    def test_five_plus_years(self):
        assert extract_yoe("Requires 5+ years of experience") == 5

    def test_three_to_five_years(self):
        assert extract_yoe("3-5 years of experience required") == 3

    def test_two_to_four_years(self):
        assert extract_yoe("2 to 4 years of experience") == 2

    def test_minimum_three_years(self):
        assert extract_yoe("Minimum 3 years of product experience") == 3

    def test_at_least_two_years(self):
        assert extract_yoe("At least 2 years experience") == 2

    def test_one_year(self):
        assert extract_yoe("1+ years of experience in product management") == 1

    def test_no_yoe_mentioned(self):
        assert extract_yoe("Great opportunity for a product manager") is None

    def test_empty_string(self):
        assert extract_yoe("") is None

    def test_none_input(self):
        assert extract_yoe(None) is None

    def test_seven_years(self):
        assert extract_yoe("7+ years of relevant experience") == 7

    def test_professional_experience(self):
        assert extract_yoe("4 years of professional experience") == 4

    def test_multiple_mentions_takes_lowest(self):
        text = "3+ years of experience preferred. 5+ years for senior track."
        assert extract_yoe(text) == 3


class TestCheckYoe:

    def test_four_years_passes(self):
        assert check_yoe("Requires 4+ years of experience") is True

    def test_three_years_passes(self):
        assert check_yoe("3 years of experience") is True

    def test_two_to_four_passes(self):
        assert check_yoe("2-4 years of experience required") is True

    def test_one_year_passes(self):
        assert check_yoe("1+ years of experience") is True

    def test_five_years_passes(self):
        assert check_yoe("5+ years of experience required") is True

    def test_six_years_rejects(self):
        assert check_yoe("6+ years of experience required") is False

    def test_seven_years_rejects(self):
        assert check_yoe("Minimum 7 years of experience") is False

    def test_ten_years_rejects(self):
        assert check_yoe("10+ years of product experience") is False

    def test_no_yoe_passes(self):
        assert check_yoe("Looking for a great product manager") is True

    def test_empty_passes(self):
        assert check_yoe("") is True


# ===================================================================
# Master filter integration
# ===================================================================

class TestPassesHardFilters:

    def test_good_job_passes(self, fake_config):
        job = {
            "title": "Associate Product Manager",
            "company": "Acme Corp",
            "location": "New York, NY",
            "description": "2+ years of experience in product management",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is True
        assert meta["title_passes"] is True
        assert meta["title_experimental"] is False
        assert meta["location_passes"] is True
        assert meta["yoe_passes"] is True
        assert meta["reject_reason"] is None

    def test_senior_title_rejects(self, fake_config):
        job = {
            "title": "Senior Product Manager",
            "company": "Acme Corp",
            "location": "New York, NY",
            "description": "",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is False
        assert meta["reject_reason"] == "title"

    def test_bad_location_rejects(self, fake_config):
        job = {
            "title": "Product Manager",
            "company": "Unknown Corp",
            "location": "San Francisco, CA",
            "description": "",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is False
        assert meta["reject_reason"] == "location"

    def test_high_yoe_rejects(self, fake_config):
        job = {
            "title": "Product Manager",
            "company": "Acme Corp",
            "location": "Remote",
            "description": "Must have 7+ years of experience in product management",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is False
        assert meta["reject_reason"] == "yoe"

    def test_target_company_outside_metro_passes(self, fake_config):
        job = {
            "title": "Product Manager",
            "company": "Stripe",
            "location": "San Francisco, CA",
            "description": "2+ years of experience",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is True
        assert meta["location_target_override"] is True

    def test_experimental_title_passes_with_flag(self, fake_config):
        job = {
            "title": "Growth Analyst",
            "company": "Acme Corp",
            "location": "New York, NY",
            "description": "",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is True
        assert meta["title_experimental"] is True

    def test_filters_short_circuit_on_title(self, fake_config):
        """Title failure should skip all other checks."""
        job = {
            "title": "Project Manager",
            "company": "Stripe",
            "location": "Remote",
            "description": "1 year experience",
            "date_posted": "2026-03-21",
        }
        passes, meta = passes_hard_filters(job, fake_config)
        assert passes is False
        assert meta["reject_reason"] == "title"
        # Location and YOE should not have been evaluated
        assert meta["location_passes"] is False
        assert meta["yoe_passes"] is False
