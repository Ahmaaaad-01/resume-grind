# Tailor resumes with ChatGPT Work

Use ChatGPT Work in this local folder as the resume editor. Paste a job description or a job link, receive an editable Word resume and a checked PDF, then request revisions in the same chat. This is the recommended workflow for the current need: individual applications and back-and-forth editing.

## Start here

1. In the desktop app, select **ChatGPT**, switch to **Work**, and use a local project with `C:\Users\fahee\resume-grind` attached. If the current chat already has folder access, you can use it directly.
2. Start with this prompt, followed by the JD:

   > Read `docs/resume-workflow/WORK_INSTRUCTIONS.md` and follow it. Tailor my resume for the job description below. Rewrite and select bullets to optimize ATS relevance and recruiter appeal, using all approved combined-bank evidence and accurate JD terminology. Keep the current profile, role split, and layout. Save an editable DOCX and a visually checked one-page PDF, check extracted-text reading order, and include short notes on key improvements and material gaps.

3. Review the PDF beside the chat. Ask for focused changes such as “make the AI evaluation work more prominent,” “keep this bullet to two lines,” or “restore the original wording about the $30M impact.” Use preview annotations when available.
4. Each revision gets a new version in `data/resume_workflow/applications/`. Name the final delivered PDF `Resume_Yahya_[company].pdf`, using a short recognizable company name, such as `Resume_Yahya_AWS.pdf`. Keep prior renders and drafts internally. Use the checked PDF when applying; keep the DOCX for later edits.

For web or cloud Work without local folder access, upload the current source PDF, recreated DOCX, current profile, approved bank, instruction file, and draft example as project sources. Local Work is easier for the included formatter because it can use the installed Times New Roman fonts. A cloud task must have the same fonts and render tools before it can claim a matching layout.

## What is ready in this folder

- `docs/resume-workflow/WORK_INSTRUCTIONS.md`: the reusable task instructions. You can also paste these into project instructions.
- `docs/resume-workflow/PROMPTS.md`: prompts for tailoring, revisions, and updating the master profile.
- `docs/resume-workflow/FORMAT.md`: measured layout and line-fit rules.
- `data/resume_workflow/current_profile.json`: current source-backed facts, including SurOps and the new AI work.
- `data/resume_workflow/approved_bank.json`: all 52 approved older bullets plus the 15 current source bullets, across six roles; includes the older summaries and skills.
- `data/resume_workflow/skills_catalog.json`: reusable skills inventory drawn from explicit skills and supported interpretations of the full evidence set, with aliases and provenance.
- `data/resume_workflow/skill_inferences.json`: reviewed source references and rationales for derived skills.
- `data/resume_workflow/source/current-resume.pdf`: the supplied source, preserved as the visual reference.
- `data/resume_workflow/template/current-resume.docx`: reconstructed editable reference.
- `data/resume_workflow/template/current-resume.pdf`: checked PDF of that reference.
- `data/resume_workflow/draft.example.json`: editable content structure for tailoring.
- `data/resume_workflow/bank-review.md`: comparison with the older 52-bullet bank.
- `scripts/build_work_resume.py`: local formatter with font-based line budgets and source-ID checks.
- `scripts/merge_resume_sources.py`: reproducible merge that keeps source IDs and current header precedence.
- `scripts/build_resume_skills.py`: refreshes the reusable skills catalog from the current profile, combined bank, and reviewed skill interpretations.
- `scripts/inspect_resume_pdf.py`: PDF extraction, layout inspection, and page previews.

Personal sources, drafts, and application outputs live under `data/`, which is already ignored by Git. The instructions and generic helpers can be tracked normally.

## Why this workflow

The existing web app already has **Submit Job** and **Manual Jobs** for pasting a JD and generating a resume. It is useful for one-click generation, but it does not provide a full editing workflow. The saved pipeline uses its original bank and formatter; Work uses the combined approved bank and the new format. Both remain available. The local API had a missing Python dependency during preview, so it is not needed for the Work route.

Work is a better fit for choosing the right achievements and revising wording interactively. The user authorizes substantial JD-driven rewrites for ATS relevance and recruiter review. The combined bank controls factual scope and results; its exact bullet wording is flexible. Better output depends on persuasive evidence selection, natural keyword alignment, accurate claims, and verification of both the rendered file and extracted-text order.

Skills are tailored too. Build them from the full approved evidence, infer demonstrated competencies with source references, and choose the methods and tools most relevant to each JD. Category labels may change; keep two clear single-line groups at the current 12-point size. After source updates, review skill interpretations and refresh the catalog before generating another resume.

The attached PDF establishes appearance, but it does not retain the original Word document's styles and settings. The included DOCX is a reconstruction. If the original Word file becomes available, use it as the template authority and compare its render before adopting it. Open and check any DOCX after manual Word edits; edits can change wrapping.

## Product documentation

- [ChatGPT Work and local files](https://learn.chatgpt.com/docs/get-started-with-work)
- [Generated file previews and annotations](https://learn.chatgpt.com/docs/artifacts-viewer)
- [Projects, shared instructions, and folder access](https://learn.chatgpt.com/docs/projects)

Reviewed October 8, 2026. Availability depends on the account and enabled tools.
