"""Build a source-backed skills catalog from explicit skills and reviewed inferences.

This does not infer with keyword matching or make model calls. The resume editor
reviews source evidence and maintains the inference records before rebuilding.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def explicit_sources(profile, bank):
    sources = {}
    for group in profile["skills"]:
        for name in group["items"]:
            sources.setdefault(name, []).append(f"profile:skill:{name}")
    for name in profile.get("additional_supported_skills", []):
        sources.setdefault(name, []).append(f"profile:additional_skill:{name}")
    for name in bank.get("approved_skills", []):
        sources.setdefault(name, []).append(f"bank:skill:{name}")
    return sources


def source_ids(profile, bank):
    valid = {ref for refs in explicit_sources(profile, bank).values() for ref in refs}
    valid.update(b["id"] for role in bank["roles"].values() for b in role["bullets"])
    valid.update(s["id"] for s in bank.get("summaries", []))
    return valid


def skill_lookup(catalog, profile, bank):
    valid = source_ids(profile, bank)
    lookup = {}
    for entry in catalog.get("skills", []):
        refs = entry.get("source_ids", [])
        if not refs or not set(refs) <= valid:
            raise ValueError(f"Skill needs valid source references: {entry.get('name')}")
        if entry.get("basis") not in ("explicit", "inferred") or not entry.get("rationale", "").strip():
            raise ValueError("Skills need an explicit/inferred basis and rationale")
        for label in [entry["name"], *entry.get("aliases", [])]:
            if not isinstance(label, str) or not label.strip() or label != label.strip() or any(c in label for c in "\n\r\t"):
                raise ValueError("Skill names and aliases must be nonempty plain text")
            key = label.casefold()
            if key in lookup and lookup[key] is not entry:
                raise ValueError(f"Ambiguous skill name or alias: {label}")
            lookup[key] = entry
    return lookup


def build_catalog(profile, bank, inferences):
    entries = {}
    for name, refs in explicit_sources(profile, bank).items():
        key = name.casefold()
        if key in entries:
            entries[key]["source_ids"].extend(refs)
        else:
            entries[key] = {"name": name, "category": "Explicit skills", "basis": "explicit",
                            "source_ids": refs, "rationale": "Listed in the approved profile or combined skill bank.",
                            "aliases": []}
    for item in inferences.get("skills", []):
        key = item["name"].casefold()
        if key in entries:
            entry = entries[key]
            entry["source_ids"].extend(item["source_ids"])
            entry["category"] = item["category"]
            entry["rationale"] += " " + item["rationale"]
            entry["aliases"].extend(item.get("aliases", []))
        else:
            entries[key] = dict(item)
    for entry in entries.values():
        entry["source_ids"] = sorted(set(entry["source_ids"]))
        entry["aliases"] = sorted(set(entry.get("aliases", [])), key=str.casefold)
    result = {"schema_version": 1,
              "policy": "User authorizes skill inference from approved sources. Inference is editorial interpretation, not a new source fact or a proficiency rating.",
              "skills": sorted(entries.values(), key=lambda s: (s["category"], s["name"].casefold()))}
    skill_lookup(result, profile, bank)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "data/resume_workflow/current_profile.json")
    parser.add_argument("--bank", type=Path, default=ROOT / "data/resume_workflow/approved_bank.json")
    parser.add_argument("--inferences", type=Path, default=ROOT / "data/resume_workflow/skill_inferences.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/resume_workflow/skills_catalog.json")
    args = parser.parse_args()
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    result = build_catalog(load(args.profile), load(args.bank), load(args.inferences))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    explicit = sum(s["basis"] == "explicit" for s in result["skills"])
    print(f"Saved {len(result['skills'])} skills ({explicit} explicit, {len(result['skills']) - explicit} inferred) to {args.output}")


if __name__ == "__main__":
    main()
