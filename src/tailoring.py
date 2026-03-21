"""Resume tailoring via LLM API — rewrite and derive bullets for JD fit.

Uses the resume bank and a job description to produce an aggressively
tailored resume JSON structure, then validates it against the bank.

Supports two providers (set in config.yaml under tailoring.provider):
  - "gemini" (default) — Google Gemini API via google-genai
  - "claude" — Anthropic Claude API via anthropic SDK
"""

import json
import logging

from src.config import get_env
from src.resume_bank import get_all_bullet_ids, get_role_bullet_ids

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an aggressive resume tailoring engine. Given a resume bank (JSON with unique IDs) and a job description, produce a one-page resume as JSON that reads like it was written specifically for this job.

PHILOSOPHY:
Your job is NOT to lightly rephrase bank bullets. Your job is to fully rewrite every bullet so it mirrors the JD's language, themes, and priorities — while staying truthful to the candidate's real experience. Every bullet should feel like the candidate wrote it after reading the JD.

ROLES:
- Include all include_always roles (the primary employer is the anchor).
- Include TWO optional roles from different companies (pick the most JD-relevant from roles where include_always is false). This ensures the resume fills a full page.
- Return primary employer roles in reverse-chronological order (they'll be grouped under one heading).

BULLET TIERS:
- "rewritten" (default): Full rewrite of one bank bullet. Change framing, emphasis, sentence structure, and language freely. Use the JD's exact terminology. Metrics and factual claims (tools used, scope, ownership) must remain truthful to the source. source_ids=[original_id], describe changes in modification field.
- "derived": Synthesize from 1-3 bullets in the SAME role. Must be provably true from sources. No invented metrics, tools, or ownership upgrades. source_ids=supporting IDs, include derivation_rationale. Use derived bullets freely when synthesizing creates a stronger JD-aligned narrative.

JD KEYWORD MIRRORING:
- Aggressively use the JD's exact phrases and terminology in bullets, summary, and skill names.
- When the JD says "cross-functional collaboration," use that exact phrase, not "worked with teams."
- When the JD says "stakeholder management," use that phrase, not "coordinated with leaders."
- ATS systems do exact-string matching. The JD's phrasing is always preferred over synonyms.

PARTIAL GAP BRIDGING:
- When the candidate has adjacent but not exact experience for a JD requirement, reframe bullets to bridge toward the gap using truthful framing.
- Example: JD asks for "marketplace experience," candidate has e-commerce API work → frame using marketplace language where truthful.
- Never fabricate experience. Flag genuine gaps in the "gaps" array.

SUMMARY:
- Pick the best-matching summary variant as an anchor (return its ID in summary_used).
- Lightly adapt it to emphasize themes relevant to the JD, but keep the candidate's actual experience, seniority, and scope accurate. Do NOT inflate years of experience, claim expertise the candidate doesn't have, or add domain knowledge not present in the bank.
- Up to 50% of the text may change — mostly word choice and emphasis, not wholesale rewriting.
- The summary should feel natural and honest, not like a sales pitch.

SKILLS:
- Reorder for JD relevance (most relevant first).
- Rename skills to match the JD's exact terminology where reasonable (e.g., "Agile/Scrum" → "Agile Methodology" if that's what the JD says).
- Return both the original bank name and the display name for each skill.
- Do NOT add skills that aren't represented in the bank.

BULLET COUNTS:
- The user prompt will tag each role as "RECENT" or "OLDER" based on master resume chronology.
- RECENT roles (the 2 most recent jobs): 3-7 bullets each.
- OLDER roles (all other jobs): maximum 2 bullets each.
- This is a hard constraint. Do not exceed these limits.

BULLET FORMATTING:
- ≤75 chars (1 line) or 120-150 chars (2 lines). Avoid 76-110 chars (orphan wrap).

JD RELEVANCE SCORING:
- Assign a jd_relevance score (1-10) to each bullet indicating how relevant it is to this specific JD.
- 10 = directly addresses a core JD requirement. 1 = tangentially related filler.
- This score is used for page-fit trimming — low-scoring bullets get cut first.

PAGE FILL: Fill exactly one page. Use the bullet count rules above. Include a 2-sentence summary.

OTHER:
- Note missing experience in "gaps" — never fabricate.

Output ONLY valid JSON matching the provided schema. No markdown fences."""

OUTPUT_SCHEMA = """\
{
  "summary_used": "<summary id>",
  "summary_text_final": "<final summary text — substantially rewritten for JD>",
  "experience": [
    {
      "role_id": "<role_id>",
      "bullets_selected": [
        {
          "source_ids": ["<bullet_id>"],
          "tier": "rewritten|derived",
          "text_final": "<final bullet text — fully rewritten for JD>",
          "derivation_rationale": "<required for derived, null for rewritten>",
          "modification": "<description of what changed from the source>",
          "jd_relevance": 8
        }
      ]
    }
  ],
  "skills_order": [
    {"original": "<bank_skill_name>", "display": "<jd_aligned_display_name>"}
  ],
  "project_included": null,
  "gaps": ["<gap description>"]
}"""


JD_ANALYSIS_PREAMBLE = """\
Before producing the tailored resume JSON, analyze the JD and include your analysis in the "jd_analysis" field:
1. Top 3-5 requirements and must-haves
2. Implicit needs (read between the lines)
3. Exact terminology and phrases to mirror
4. Gaps between candidate's experience and JD requirements

Then produce the resume JSON with the jd_analysis field populated."""


def _build_user_prompt(bank: dict, jd_text: str, config: dict) -> str:
    """Build the user message with resume bank and JD."""
    tailoring_cfg = config.get("tailoring", {})
    use_preamble = tailoring_cfg.get("jd_analysis_preamble", False)
    recent_limits = tailoring_cfg.get("recent_jobs_bullet_limits", {"min": 3, "max": 7})
    older_limits = tailoring_cfg.get("older_jobs_bullet_limits", {"max": 2})

    preamble = f"\n\n## Instructions\n\n{JD_ANALYSIS_PREAMBLE}" if use_preamble else ""

    # Annotate roles as RECENT or OLDER
    recent_ids = _get_recent_role_ids(bank)
    role_tags = []
    for role in bank.get("experience", []):
        rid = role["role_id"]
        tag = "RECENT" if rid in recent_ids else "OLDER"
        role_tags.append(f"- {rid}: {tag} ({role.get('company', '')} — {role.get('title', '')})")
    role_annotation = "\n".join(role_tags)

    return f"""## Resume Bank

{json.dumps(bank, indent=2)}

## Job Description

{jd_text}

## Role Recency Tags (for bullet count rules)

{role_annotation}

RECENT roles: {recent_limits['min']}-{recent_limits['max']} bullets each.
OLDER roles: max {older_limits['max']} bullets each.

## Output Schema

{OUTPUT_SCHEMA}{preamble}

Produce the tailored resume JSON. Respect the bullet count limits above. Include 2 optional roles from different companies. All source_ids must reference real bank bullet IDs. Rewrite every bullet aggressively for this JD. Output ONLY the JSON."""


def _call_claude(user_prompt: str) -> str:
    """Call Anthropic Claude API and return raw text response."""
    import anthropic

    api_key = get_env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    tailoring_cfg = _get_tailoring_config()
    model = tailoring_cfg.get("claude_model", "claude-sonnet-4-20250514")

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def _call_gemini(user_prompt: str) -> str:
    """Call Google Gemini API and return raw text response."""
    from google import genai

    api_key = get_env("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    tailoring_cfg = _get_tailoring_config()
    model = tailoring_cfg.get("gemini_model", "gemini-2.5-flash")

    response = client.models.generate_content(
        model=model,
        contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
        config={
            "temperature": 0.3,
            "max_output_tokens": 16384,
        },
    )
    return response.text.strip()


# Module-level config cache (set during tailor_resume call)
_current_config: dict = {}


def _get_tailoring_config() -> dict:
    return _current_config.get("tailoring", {})


def _strip_markdown_fences(raw_text: str) -> str:
    """Strip markdown fences if the LLM added them despite instructions."""
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines)
    return raw_text


def tailor_resume(job: dict, jd_text: str, bank: dict, config: dict) -> dict:
    """Call LLM API to tailor a resume for a specific job.

    Args:
        job: Normalized job dict (title_raw, company, etc.)
        jd_text: Full job description text.
        bank: Loaded and validated resume bank.
        config: Application config dict.

    Returns:
        Dict with tailored resume structure and validation_errors list.
    """
    global _current_config
    _current_config = config

    tailoring_cfg = config.get("tailoring", {})
    provider = tailoring_cfg.get("provider", "gemini")

    user_prompt = _build_user_prompt(bank, jd_text, config)

    log.info("Tailoring resume for %s at %s (provider=%s)",
             job.get("title_raw", "?"), job.get("company", "?"), provider)

    if provider == "claude":
        raw_text = _call_claude(user_prompt)
    elif provider == "gemini":
        raw_text = _call_gemini(user_prompt)
    else:
        return {"validation_errors": [f"Unknown tailoring provider: {provider}"]}

    raw_text = _strip_markdown_fences(raw_text)

    try:
        tailored = json.loads(raw_text)
    except json.JSONDecodeError as e:
        log.error("LLM returned invalid JSON: %s", e)
        log.debug("Raw response: %s", raw_text[:500])
        return {
            "raw_response": raw_text,
            "validation_errors": [f"LLM returned invalid JSON: {e}"],
        }

    # Validate
    errors = validate_tailored_output(tailored, bank)
    tailored["validation_errors"] = errors
    if errors:
        log.warning("Tailoring validation errors for %s: %s",
                     job.get("company", "?"), errors)
    else:
        log.info("Tailoring validation passed for %s", job.get("company", "?"))

    return tailored


_SINGLE_SOURCE_TIERS = {"rewritten", "rephrased", "selected"}


def validate_tailored_output(tailored: dict, bank: dict) -> list[str]:
    """Validate a tailored resume output against the resume bank.

    Returns list of error strings (empty = valid).
    """
    errors: list[str] = []
    bank_ids = get_all_bullet_ids(bank)

    for role in tailored.get("experience", []):
        role_id = role.get("role_id", "unknown")
        role_bullet_ids = get_role_bullet_ids(bank, role_id)

        # Check role_id exists in bank
        bank_role_ids = {r["role_id"] for r in bank.get("experience", [])}
        if role_id not in bank_role_ids:
            errors.append(f"INVALID role_id: {role_id} not found in resume bank")

        for bullet in role.get("bullets_selected", []):
            tier = bullet.get("tier", "rewritten")
            sids = bullet.get("source_ids", [])

            # Check all source_ids exist
            for sid in sids:
                if sid not in bank_ids:
                    errors.append(f"INVALID source_id: {sid} not found in resume bank")

            if tier == "derived":
                if len(sids) < 1 or len(sids) > 3:
                    errors.append(
                        f"DERIVED bullet has {len(sids)} source_ids (must be 1-3): "
                        f"{bullet.get('text_final', '')[:60]}..."
                    )
                # All source bullets must be from the same role
                for sid in sids:
                    if sid not in role_bullet_ids and sid in bank_ids:
                        errors.append(
                            f"DERIVED bullet references {sid} which belongs to a "
                            f"different role than {role_id}"
                        )
                if not bullet.get("derivation_rationale"):
                    errors.append(
                        f"DERIVED bullet missing derivation_rationale: "
                        f"{bullet.get('text_final', '')[:60]}..."
                    )
            elif tier in _SINGLE_SOURCE_TIERS:
                if len(sids) != 1:
                    errors.append(
                        f"{tier.upper()} bullet must have exactly 1 source_id, "
                        f"got {len(sids)}"
                    )

            # Soft warning for missing jd_relevance
            if bullet.get("jd_relevance") is None:
                log.warning("Bullet missing jd_relevance: %s",
                            bullet.get("text_final", "")[:60])

    # Validate bullet counts per role (recent vs older)
    recent_ids = _get_recent_role_ids(bank)
    tailoring_cfg = _get_tailoring_config()
    recent_limits = tailoring_cfg.get("recent_jobs_bullet_limits", {"min": 3, "max": 7})
    older_limits = tailoring_cfg.get("older_jobs_bullet_limits", {"max": 2})

    for role in tailored.get("experience", []):
        role_id = role.get("role_id", "unknown")
        n_bullets = len(role.get("bullets_selected", []))
        if role_id in recent_ids:
            if n_bullets > recent_limits["max"]:
                errors.append(
                    f"RECENT role {role_id} has {n_bullets} bullets "
                    f"(max {recent_limits['max']})"
                )
        else:
            if n_bullets > older_limits["max"]:
                errors.append(
                    f"OLDER role {role_id} has {n_bullets} bullets "
                    f"(max {older_limits['max']})"
                )

    # Validate summary reference
    summary_used = tailored.get("summary_used")
    if summary_used:
        summary_ids = {s["id"] for s in bank.get("summaries", [])}
        if summary_used not in summary_ids:
            errors.append(f"INVALID summary_used: {summary_used} not in resume bank")

    # Warn (not error) if no non-always role is included
    tailored_role_ids = {r.get("role_id") for r in tailored.get("experience", [])}
    bank_optional_ids = {r["role_id"] for r in bank.get("experience", [])
                         if not r.get("include_always", True)}
    if bank_optional_ids and not tailored_role_ids & bank_optional_ids:
        log.warning("No optional (include_always=false) role included in tailored resume")

    return errors


def _get_recent_role_ids(bank: dict, count: int = 2) -> set[str]:
    """Return role_ids for the N most recent jobs based on master resume chronology."""
    sorted_roles = sorted(
        bank.get("experience", []),
        key=lambda r: (
            r.get("end_date", "") if r.get("end_date", "") != "present" else "9999-12",
            r.get("start_date", ""),
        ),
        reverse=True,
    )
    return {r["role_id"] for r in sorted_roles[:count]}
