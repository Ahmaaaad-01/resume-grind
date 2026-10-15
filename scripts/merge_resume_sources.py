"""Combine the approved older fact bank with the current resume source.

Keeps source IDs and source text; the current profile controls rendered headers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_MAP = {
    "co-pm-ai-servicing": "co-servicing-ai",
    "co-pm-data-personalization": "co-data-products",
    "co-intern-process": "co-process-intern",
    "intelsat-fpa": "intelsat-intern",
    "dmv-marketing": "dmv-marketing",
}


def date_label(value):
    if value.lower() in ("present", "current"):
        return "Current"
    if len(value) == 7 and value[4] == "-":
        months = "January February March April May June July August September October November December".split()
        return f"{months[int(value[5:]) - 1]} {value[:4]}"
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "data/resume_workflow/current_profile.json")
    parser.add_argument("--legacy", type=Path, default=ROOT / "data/master_resume/resume_bank.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/resume_workflow/approved_bank.json")
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    legacy = json.loads(args.legacy.read_text(encoding="utf-8"))
    result = {
        "schema_version": 1,
        "approval": "User explicitly approved all older-bank facts for future jobs on 2026-10-08, together with the current resume information.",
        "precedence": "Current profile controls contact, titles, displayed dates, role split, and default layout. Older bank supplies approved additional evidence, including optional DMV history.",
        "roles": {},
        "optional_groups": [],
        "summaries": legacy.get("summaries", []),
        "legacy_education": legacy.get("education", []),
        "legacy_metadata": legacy.get("meta", {}),
    }
    for section in profile["sections"]:
        for group in section["groups"]:
            for role in group["roles"]:
                result["roles"][role["id"]] = {
                    "title": role["title"], "company": group["company"],
                    "bullets": [dict(b, provenance="current_resume") for b in role["bullets"]],
                }
    current_ids = set(result["roles"])
    for old_role in legacy["experience"]:
        mapped = ROLE_MAP.get(old_role["role_id"])
        if not mapped:
            raise ValueError(f"Map the new legacy role before merging: {old_role['role_id']}")
        if mapped not in current_ids:
            layout_role = {
                "id": mapped, "title": old_role["title"],
                "date_display": f"{date_label(old_role['start_date'])} - {date_label(old_role['end_date'])}",
                "bullets": [], "optional": True,
            }
            result["optional_groups"].append({"company": old_role["company"],
                                              "location": old_role["location"], "roles": [layout_role]})
            result["roles"][mapped] = {"title": old_role["title"], "company": old_role["company"], "bullets": []}
        result["roles"][mapped]["legacy_role_metadata"] = {k: v for k, v in old_role.items() if k != "bullets"}
        for item in old_role["bullets"]:
            result["roles"][mapped]["bullets"].append(dict(item, max_lines=2, provenance="legacy_bank"))
    skills = {item for group in profile["skills"] for item in group["items"]}
    skills.update(profile.get("additional_supported_skills", []))
    skills.update(item["skill"] for category in legacy["skills"].values() for item in category)
    result["approved_skills"] = sorted(skills, key=str.casefold)
    all_ids = [b["id"] for role in result["roles"].values() for b in role["bullets"]]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Duplicate evidence IDs in combined bank")
    result["source_bullet_count"] = len(all_ids)
    result["note"] = "Multiple source bullets can describe the same achievement. Do not count them as independent outcomes or repeat one achievement just to fill space."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Combined {len(all_ids)} source bullets across {len(result['roles'])} roles; {len(result['approved_skills'])} supported skill labels.")


if __name__ == "__main__":
    main()
