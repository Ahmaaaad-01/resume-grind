"""Check the current workflow's skill provenance and formatting boundaries."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_resume_skills import build_catalog, skill_lookup
from build_work_resume import build, register_font, validate


class WorkResumeSkillsTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "sections": [{"groups": [{"roles": [{"id": "test-role", "bullets": []}]}]}],
            "skills": [{"label": "Programming", "items": ["Python"]},
                       {"label": "Platforms", "items": ["Jira"]}],
        }
        self.bank = {"roles": {"test-role": {"bullets": [{"id": "s1", "text": "Built AI evaluation metrics."}]}},
                     "approved_skills": ["Python", "Jira"]}
        self.inferences = {"skills": [{"name": "AI Evaluation", "category": "AI", "basis": "inferred",
                                        "source_ids": ["s1"], "rationale": "Built an evaluation framework.",
                                        "aliases": ["AI Evaluation Frameworks"]}]}
        self.catalog = build_catalog(self.profile, self.bank, self.inferences)
        self.draft = {"role_bullets": {"test-role": []},
                      "skills": [{"label": "Product & AI", "items": ["AI Evaluation Frameworks"]},
                                 {"label": "Technical", "items": ["Python"]}]}

    def test_supported_inference_alias_and_new_labels(self):
        report = validate(self.profile, self.draft, self.bank, self.catalog)
        self.assertEqual(report[0]["canonical"], "AI Evaluation")
        self.assertEqual(report[0]["source_ids"], ["s1"])
        self.assertEqual(report[0]["basis"], "inferred")

    def test_legacy_skill_lists_still_work(self):
        self.draft["skills"] = copy.deepcopy(self.profile["skills"])
        self.assertEqual(len(validate(self.profile, self.draft, self.bank)), 2)

    def test_unlisted_tool_is_rejected(self):
        self.draft["skills"][1]["items"] = ["LangChain"]
        with self.assertRaisesRegex(ValueError, "source-backed catalog"):
            validate(self.profile, self.draft, self.bank, self.catalog)

    def test_stale_source_reference_is_rejected(self):
        self.inferences["skills"][0]["source_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "valid source references"):
            build_catalog(self.profile, self.bank, self.inferences)

    def test_duplicate_alias_selection_is_rejected(self):
        self.draft["skills"][1]["items"] = ["AI Evaluation"]
        with self.assertRaisesRegex(ValueError, "Duplicate skill or alias"):
            validate(self.profile, self.draft, self.bank, self.catalog)

    def test_ambiguous_alias_is_rejected(self):
        self.inferences["skills"][0]["aliases"] = ["Python"]
        with self.assertRaisesRegex(ValueError, "Ambiguous skill"):
            build_catalog(self.profile, self.bank, self.inferences)

    def test_labels_and_two_line_structure(self):
        self.draft["skills"][1]["label"] = "product & ai"
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate(self.profile, self.draft, self.bank, self.catalog)
        self.draft["skills"].pop()
        with self.assertRaisesRegex(ValueError, "two skill lines"):
            validate(self.profile, self.draft, self.bank, self.catalog)


if __name__ == "__main__":
    unittest.main()
