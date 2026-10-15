# Current resume format and line limits

The reference is `data/resume_workflow/source/current-resume.pdf`. Preserve the design and overall density; exact Word settings were reconstructed because the supplied file is a PDF.

| Element | Required appearance |
| --- | --- |
| Page | Exactly one US Letter page, portrait, 612 x 792 points |
| Body | Times New Roman, 12 pt, black |
| Name | Centered, Times New Roman 20 pt, regular weight |
| Contact | One centered 12 pt line, current profile fields |
| Main horizontal span | Approximately x=36 to x=576 pt, 0.5-inch side margins |
| Bullet text | Starts at x=54 pt; hanging bullet at x=36; about 522 pt usable text width |
| Line height | Approximately 14.32 pt within wrapped bullets; about 0.5 pt paragraph gap |
| Company headers | Bold left company; bold location aligned right |
| Role headers | Italic left title; regular right date |
| Header alignment | Simple inline borderless two-cell rows, left text aligned left and location/date aligned right at x=576 pt; no tab-dependent spacing |
| Sections | Work Experience, Entrepreneurship, Skills, Education |
| Dividers | Thin gray rules before Work Experience, Entrepreneurship, and Skills |
| Bottom | Reference ends near y=734 pt from the top; aim for roughly y=715-742 when enough relevant content exists |

Most bullets should occupy one or two rendered lines. The current Claude-workflow bullet uses three lines; this is an exception rather than the default. Set line budgets for the tailored bullet's content and the full page; the source bullet's original wording and line count do not restrict a supported rewrite. Target a final line with at least about half the available width; avoid a new line containing only a few words. The helper flags final lines below 30% of the bullet width. Improve phrasing or pick evidence, rather than widening the page or reducing type.

The baseline has 15 work/entrepreneurship bullets occupying 26 lines. Tailoring can change the count for relevance; that count is not permission to fill the page with unsupported material. Keep a legible page with similar density, including the Data Products and SurOps sections.

The Skills section contains two single-line bullets at the existing body font, indent, and spacing. Category labels and items may change to suit the JD; Programming/Platforms is not mandatory. Use concise descriptive categories, such as Product & AI and Technical. Keep methods and tools logically grouped, avoid redundant aliases, and measure the full label plus items. Select fewer or shorter supported skills if a line overflows. Never shrink the font or expand the margins to fit a skills list.

## Acceptance check on the actual PDF

- One page; no extra blank page.
- Times New Roman remains 12 pt in all body text. No font substitution.
- All bullets fit their intended one/two-line budget, with a deliberate three-line exception only when warranted.
- Continuation lines align with bullet text, not the bullet symbol.
- No overlap, clipped text, awkward orphan words, missing glyphs, or dates colliding with titles.
- Company locations and dates align to the right; Capital One's overall date and source role split are retained.
- Every displayed location and date must end at the same x=576 pt right edge within 0.5 pt in the final PDF and remain right-aligned in the DOCX preview. Use simple borderless header rows with zero cell margins; body achievements stay in ordinary paragraphs. Check each header individually rather than relying on global text bounds.
- Text stays inside the reference's horizontal bounds; education and certification fit comfortably above the bottom edge.
- Names, contact details, dates, metrics, and certifications match current sources.
- The PDF was rendered from the final DOCX, and the latest page image was visually reviewed.
- DOCX paragraph order and PDF text extraction preserve complete, readable contact, employer, role, date, achievement, skills, and education text. Keep important content out of tables, text boxes, headers, and footers.
- Both tailored skills lines fit on one line each, with readable category labels, no clipping or redundant synonyms, and catalog provenance for every selected item.

Hard line breaks in the generated DOCX stabilize current wrapping. After substantial direct Word edits, rebuild from the JSON or remove and recompute those breaks, then render again. Opening the file on another system can change font rendering; use the checked PDF as the application artifact.
