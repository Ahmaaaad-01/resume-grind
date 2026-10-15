# Prompts for the resume workflow

## Tailor a resume

```text
Read docs/resume-workflow/WORK_INSTRUCTIONS.md and follow it.
Tailor my current resume for [company] — [role]. Use the current layout and all
approved facts from both the older bank and the new resume.
Rewrite, combine, select, and reorder supported bullets as needed to optimize
for ATS relevance and recruiter review. Use the JD's terminology naturally
where it accurately describes my work; preserve actual scope and results.
Build and tailor my skills from the source-backed catalog, including reasonable
inferences from demonstrated work. Choose the most relevant methods and tools
for this JD and rename/regroup the two skills lines as needed. Preserve skill
provenance and the existing font, margins, and one-page layout.
Create the editable DOCX and a checked one-page PDF named
Resume_Yahya_[company].pdf (for AWS: Resume_Yahya_AWS.pdf). Keep the Capital One
Servicing AI / Data Products split and SurOps. Fit the tailored bullets to
the one-page layout without reducing the font. Check extracted-text reading
order as well as appearance. Explain only the key improvements and material gaps.

Job description:
[paste the full JD, or give the posting link]
```

## Revise the emphasis

```text
Revise the last resume to emphasize [AI evaluation / platform delivery / data
products / customer discovery]. Use the strongest supported evidence, keep the
claims accurate, and avoid generic JD keyword stuffing. Save a new version and
re-render it before returning the DOCX and PDF.
```

## Fix line fit

```text
This bullet ends with a short dangling line: [paste bullet]. Tighten it into
two lines at the existing 12-point Times New Roman layout. Preserve its scope,
metric, and ownership. Rebuild and check the actual PDF, keeping the other
bullets as close as possible to the prior revision.
```

## Tailor the skills

```text
Update the skills section for this JD using the entire approved source set.
Refresh the skills catalog if needed. Infer demonstrated competencies with
supporting source IDs, select relevant methods and tools, and use two clear
categories suited to the role. Keep both lines to one rendered line each at
12 pt. Save a new version, render it, and check the full page and extraction.
```

## Update the master profile

```text
I have attached a new current resume. Compare it with
data/resume_workflow/current_profile.json. Update the source-backed profile,
identify material conflicts, and preserve verified historical source IDs.
Use the new resume's structure unless I say otherwise. Rebuild and check the
editable reference and its one-page PDF. Keep job-specific rewrites separate
from the master facts.
```

## Review older bank evidence

```text
Review the combined approved bank for older evidence that could improve this
JD's fit. All older bank facts are already approved. Show which source IDs and
roles you selected, avoid duplicate achievements, then tailor and render a
new version in the current format.
```
