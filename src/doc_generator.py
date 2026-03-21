"""DOCX resume generation from tailored JSON output.

Spec: Times New Roman 12pt, 0.7" margins, single column, 1-page hard constraint.
Sections: Contact → Summary → Experience → Skills → Education → Projects (optional)

Page-fit strategy: generate DOCX → render to PDF → measure page count → trim if
overflow → repeat. PDF is the layout truth; DOCX remains the editable master output.
"""

import logging
import re
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml.ns import qn

from src.config import PROJECT_ROOT

log = logging.getLogger(__name__)

# Layout constants
MARGIN = Inches(0.7)
FONT_NAME = "Times New Roman"
NAME_SIZE = Pt(16)
HEADER_SIZE = Pt(12)
BODY_SIZE = Pt(12)
BULLET_INDENT = Inches(0.25)
BULLET_SPACING = Pt(6)
LINE_SPACING = 1.0
# Tab stop position in twips (1 inch = 1440 twips). 7.1" usable width.
RIGHT_TAB_TWIPS = int(7.1 * 1440)  # 10224 twips

# Page geometry for heuristic estimation (used for logging/diagnostics only)
CHARS_PER_LINE = 73              # Times New Roman 12pt at 7.1" (accounting for bullet indent)
LINE_HEIGHT_PT = 15.0            # TNR 12pt actual rendered line height in Word (single-spaced)
MAX_CONTENT_LINES = 65.0         # heuristic max (not used for page-fit decisions)

# PDF render-measure-adjust loop settings
MAX_TRIM_PASSES = 8              # max bullet-trim iterations
MIN_BULLETS_PER_ROLE = 2         # don't trim a role below this


def _add_right_tab_stop(paragraph, twips=RIGHT_TAB_TWIPS):
    """Insert a right-aligned tab stop at the given position (in twips)."""
    pPr = paragraph._p.get_or_add_pPr()
    tabs = pPr.makeelement(qn('w:tabs'), {})
    tab = tabs.makeelement(qn('w:tab'), {
        qn('w:val'): 'right',
        qn('w:pos'): str(twips),
    })
    tabs.append(tab)
    pPr.append(tabs)


def _set_font(run, size=BODY_SIZE, bold=False, italic=False):
    """Apply font settings to a run."""
    run.font.name = FONT_NAME
    run.font.size = size
    run.font.bold = bold
    run.font.italic = italic
    # Force font for East Asian text too
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = rPr.makeelement(qn('w:rFonts'), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), FONT_NAME)


def _add_section_header(doc, title):
    """Add an ALL CAPS bold section header with a thin bottom border."""
    para = doc.add_paragraph()
    para.space_before = Pt(6)
    para.space_after = Pt(3)
    para.paragraph_format.line_spacing = LINE_SPACING
    run = para.add_run(title.upper())
    _set_font(run, size=HEADER_SIZE, bold=True)

    # Add thin bottom border
    pPr = para._p.get_or_add_pPr()
    pBdr = pPr.makeelement(qn('w:pBdr'), {})
    bottom = pBdr.makeelement(qn('w:bottom'), {
        qn('w:val'): 'single',
        qn('w:sz'): '4',
        qn('w:space'): '1',
        qn('w:color'): '000000',
    })
    pBdr.append(bottom)
    pPr.append(pBdr)

    return para


def _add_bullet(doc, text):
    """Add a bullet point paragraph."""
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = BULLET_INDENT
    para.paragraph_format.space_after = BULLET_SPACING
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.line_spacing = LINE_SPACING

    # Add bullet character
    run = para.add_run("• ")
    _set_font(run)
    run = para.add_run(text)
    _set_font(run)

    return para


def _add_contact_section(doc, contact):
    """Add centered name and contact line."""
    # Name
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_para.space_after = Pt(2)
    run = name_para.add_run(contact.get("name", ""))
    _set_font(run, size=NAME_SIZE, bold=True)

    # Contact line: email | phone | LinkedIn | location
    parts = []
    for field in ("email", "phone", "linkedin", "location"):
        val = contact.get(field, "")
        if val:
            parts.append(val)
    contact_para = doc.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    contact_para.space_after = Pt(4)
    run = contact_para.add_run(" | ".join(parts))
    _set_font(run)


def _add_summary_section(doc, summary_text):
    """Add summary section."""
    _add_section_header(doc, "Summary")
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(4)
    para.paragraph_format.line_spacing = LINE_SPACING
    run = para.add_run(summary_text)
    _set_font(run)


def _format_date_range(start_date, end_date):
    """Format date range for display (e.g., 'Jan 2024 – Present')."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def fmt(d):
        if not d or d.lower() == "present":
            return "Present"
        parts = d.split("-")
        if len(parts) == 2:
            year, month = parts
            month_idx = int(month) - 1
            if 0 <= month_idx < 12:
                return f"{months[month_idx]} {year}"
        return d

    return f"{fmt(start_date)} – {fmt(end_date)}"


def _group_roles_by_company(tailored_roles, bank_roles):
    """Group consecutive tailored roles by company name, preserving order.

    Returns list of (company, location, [(role_entry, bank_role), ...]).
    """
    groups = []
    for role_entry in tailored_roles:
        role_id = role_entry.get("role_id", "")
        bank_role = bank_roles.get(role_id, {})
        company = bank_role.get("company", "")
        location = bank_role.get("location", "")

        if groups and groups[-1][0] == company:
            groups[-1][2].append((role_entry, bank_role))
        else:
            groups.append((company, location, [(role_entry, bank_role)]))

    return groups


def _add_single_role(doc, role_entry, bank_role):
    """Render a single-role experience entry (company — title \\t dates | loc)."""
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.line_spacing = LINE_SPACING
    _add_right_tab_stop(para)

    run = para.add_run(bank_role.get("company", ""))
    _set_font(run, bold=True)
    run = para.add_run(" — ")
    _set_font(run)
    run = para.add_run(bank_role.get("title", ""))
    _set_font(run, italic=True)

    date_range = _format_date_range(
        bank_role.get("start_date", ""),
        bank_role.get("end_date", ""),
    )
    location = bank_role.get("location", "")
    date_loc = f"{date_range} | {location}" if location else date_range
    run = para.add_run(f"\t{date_loc}")
    _set_font(run)

    for bullet in role_entry.get("bullets_selected", []):
        _add_bullet(doc, bullet.get("text_final", ""))


def _add_multi_role_group(doc, company, location, roles):
    """Render a multi-role company group (e.g. employer with 2-3 sub-roles)."""
    # Company header line: Company name left, location right-aligned
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.line_spacing = LINE_SPACING
    _add_right_tab_stop(para)

    run = para.add_run(company)
    _set_font(run, bold=True)
    if location:
        run = para.add_run(f"\t{location}")
        _set_font(run)

    # Each sub-role: indented title left, date range right-aligned
    for role_entry, bank_role in roles:
        role_para = doc.add_paragraph()
        role_para.paragraph_format.left_indent = BULLET_INDENT
        role_para.paragraph_format.space_after = Pt(2)
        role_para.paragraph_format.space_before = Pt(2)
        role_para.paragraph_format.line_spacing = LINE_SPACING
        _add_right_tab_stop(role_para)

        run = role_para.add_run(bank_role.get("title", ""))
        _set_font(run, italic=True)

        date_range = _format_date_range(
            bank_role.get("start_date", ""),
            bank_role.get("end_date", ""),
        )
        run = role_para.add_run(f"\t{date_range}")
        _set_font(run)

        for bullet in role_entry.get("bullets_selected", []):
            _add_bullet(doc, bullet.get("text_final", ""))


def _add_experience_section(doc, tailored, bank):
    """Add experience section with tailored bullets, grouping multi-role companies."""
    _add_section_header(doc, "Experience")

    bank_roles = {r["role_id"]: r for r in bank.get("experience", [])}
    groups = _group_roles_by_company(tailored.get("experience", []), bank_roles)

    for company, location, roles in groups:
        if len(roles) == 1:
            _add_single_role(doc, roles[0][0], roles[0][1])
        else:
            _add_multi_role_group(doc, company, location, roles)


def _parse_skills_order(skills_order):
    """Parse skills_order into (order_keys, display_map).

    Handles both old format (list of strings) and new format
    (list of {"original": ..., "display": ...} dicts).
    """
    if not skills_order:
        return [], {}
    if isinstance(skills_order[0], dict):
        order_keys = [s["original"] for s in skills_order]
        display_map = {s["original"]: s["display"] for s in skills_order}
    else:
        order_keys = skills_order
        display_map = {}
    return order_keys, display_map


def _add_skills_section(doc, tailored, bank):
    """Add skills section, reordered and optionally renamed per tailoring."""
    _add_section_header(doc, "Skills")

    skills_order = tailored.get("skills_order", [])
    order_keys, display_map = _parse_skills_order(skills_order)
    bank_skills = bank.get("skills", {})

    def reorder(category_skills):
        ordered = [s for s in order_keys if s in category_skills]
        remaining = [s for s in category_skills if s not in ordered]
        return ordered + remaining

    def display(skill):
        return display_map.get(skill, skill)

    tech = reorder([s["skill"] for s in bank_skills.get("technical", [])])
    platform = reorder([s["skill"] for s in bank_skills.get("platform", [])])

    if tech:
        para = doc.add_paragraph()
        para.paragraph_format.line_spacing = LINE_SPACING
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run("Technical: ")
        _set_font(run, bold=True)
        run = para.add_run(", ".join(display(s) for s in tech))
        _set_font(run)

    if platform:
        para = doc.add_paragraph()
        para.paragraph_format.line_spacing = LINE_SPACING
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run("Platform: ")
        _set_font(run, bold=True)
        run = para.add_run(", ".join(display(s) for s in platform))
        _set_font(run)

    if not tech and not platform:
        para = doc.add_paragraph()
        para.paragraph_format.line_spacing = LINE_SPACING
        all_skills = []
        for cat in ("technical", "platform"):
            all_skills.extend(s["skill"] for s in bank_skills.get(cat, []))
        run = para.add_run(", ".join(display(s) for s in all_skills))
        _set_font(run)


def _add_education_section(doc, bank):
    """Add education section."""
    education = bank.get("education", [])
    if not education:
        return

    _add_section_header(doc, "Education")

    for edu in education:
        if not edu.get("include_always", True):
            continue

        # Line 1: School (bold, left) \t Location (right)
        line1 = doc.add_paragraph()
        line1.paragraph_format.line_spacing = LINE_SPACING
        line1.paragraph_format.space_after = Pt(0)
        _add_right_tab_stop(line1)

        run = line1.add_run(edu.get("school", ""))
        _set_font(run, bold=True)

        location = edu.get("location", "")
        if location:
            run = line1.add_run(f"\t{location}")
            _set_font(run)

        # Line 2: Degree (left) \t Graduation (right)
        line2 = doc.add_paragraph()
        line2.paragraph_format.line_spacing = LINE_SPACING
        line2.paragraph_format.space_after = Pt(2)
        _add_right_tab_stop(line2)

        degree = edu.get("degree", "")
        honors = edu.get("honors")
        degree_text = degree
        if honors:
            degree_text += f" ({honors})"
        run = line2.add_run(degree_text)
        _set_font(run, italic=bool(honors))

        grad = edu.get("graduation", "")
        if grad:
            run = line2.add_run(f"\t{grad}")
            _set_font(run)


def _add_projects_section(doc, tailored, bank):
    """Add projects section if one was included."""
    project_id = tailored.get("project_included")
    if not project_id:
        return

    projects = {p["id"]: p for p in bank.get("projects", [])}
    project = projects.get(project_id)
    if not project:
        return

    _add_section_header(doc, "Projects")

    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.line_spacing = LINE_SPACING

    run = para.add_run(project.get("name", ""))
    _set_font(run, bold=True)

    context = project.get("context", "")
    if context:
        run = para.add_run(f" — {context}")
        _set_font(run, italic=True)

    for bullet in project.get("bullets", []):
        _add_bullet(doc, bullet.get("text", ""))


def _sanitize_filename(text):
    """Remove characters not safe for filenames."""
    return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '_')


def generate_resume_filename(bank, job):
    """Generate filename per spec: {First}_{Last}_Resume_{Company}_{Title}.docx"""
    name = bank.get("contact", {}).get("name", "Candidate")
    parts = name.split()
    first = parts[0] if parts else "First"
    last = parts[-1] if len(parts) > 1 else "Last"

    company = _sanitize_filename(job.get("company", "Company"))
    title = _sanitize_filename(job.get("title_raw", "PM"))

    # Shorten title for filename
    if len(title) > 30:
        title = title[:30].rstrip('_')

    return f"{first}_{last}_Resume_{company}_{title}.docx"


def _estimate_content_lines(doc):
    """Estimate total content height in line-equivalents (heuristic, for logging only).

    Not used for page-fit decisions — PDF rendering is the source of truth.
    """
    total_lines = 0.0
    for para in doc.paragraphs:
        text = para.text
        font_size_pt = 12.0
        if para.runs:
            run_size = para.runs[0].font.size
            if run_size:
                font_size_pt = run_size / 12700

        if not text.strip():
            text_lines = 0.0
        else:
            effective_len = len(text)
            if text.startswith("• "):
                effective_len = len(text) - 2
            text_lines = max(1, -(-effective_len // CHARS_PER_LINE))

        height_scale = font_size_pt / 12.0
        fmt = para.paragraph_format
        space_before_pt = (fmt.space_before or Pt(0)) / 12700
        space_after_pt = (fmt.space_after or Pt(0)) / 12700
        spacing_lines = (space_before_pt + space_after_pt) / LINE_HEIGHT_PT

        total_lines += (text_lines * height_scale) + spacing_lines

    return total_lines


def _find_libreoffice() -> str | None:
    """Find the LibreOffice soffice executable on the system."""
    import shutil
    # Check PATH first
    soffice = shutil.which("soffice")
    if soffice:
        return soffice
    # Common Windows install locations
    for path in [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
    ]:
        if path.exists():
            return str(path)
    return None


def _render_to_pdf(docx_path: Path, pdf_path: Path | None = None) -> Path:
    """Convert DOCX to PDF using LibreOffice headless mode.

    Falls back to docx2pdf (Word COM) if LibreOffice is not available.
    Returns the path to the generated PDF.
    """
    import subprocess

    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")

    soffice = _find_libreoffice()
    if soffice:
        # LibreOffice outputs to a directory, not a specific file
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", str(docx_path.parent), str(docx_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")
        # LibreOffice names the output same as input but with .pdf extension
        lo_output = docx_path.with_suffix(".pdf")
        if lo_output != pdf_path and lo_output.exists():
            lo_output.rename(pdf_path)
        if not pdf_path.exists():
            raise RuntimeError(f"LibreOffice did not produce {pdf_path}")
        return pdf_path

    # Fallback: try docx2pdf (Word COM)
    from docx2pdf import convert
    convert(str(docx_path), str(pdf_path))
    return pdf_path


def _count_pdf_pages(pdf_path: Path) -> int:
    """Count pages in a PDF file."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


ORPHAN_MIN = CHARS_PER_LINE + 1   # 76 — start of orphan zone
ORPHAN_MAX = 110                  # end of orphan zone
# Break points for trimming orphan-zone bullets (tried in order)
_BREAK_PATTERNS = [", including ", ", enabling ", ", ensuring ", ", helping ",
                   ", driving ", ", resulting ", ", coordinating ", ", and ", ", "]


def _reflow_bullets(doc):
    """Trim bullets in the orphan zone (76-110 chars) to fit on one line.

    Finds a natural break point (comma clause) and truncates there.
    Bullets ≤75 or ≥111 chars are left alone.
    """
    for para in doc.paragraphs:
        if not para.text.startswith("• "):
            continue
        # Get the bullet text (after "• ")
        full_text = para.text[2:]
        length = len(full_text)

        if length < ORPHAN_MIN or length > ORPHAN_MAX:
            continue  # fine as-is

        # Try to trim at a natural break point to get ≤ CHARS_PER_LINE
        trimmed = None
        for pattern in _BREAK_PATTERNS:
            idx = full_text.rfind(pattern)
            if idx > 0 and idx <= CHARS_PER_LINE:
                trimmed = full_text[:idx]
                break

        if trimmed and trimmed != full_text:
            log.debug("Reflowed bullet: %d→%d chars", length, len(trimmed))
            # Rewrite the paragraph runs
            for run in para.runs:
                run.text = ""
            para.runs[0].text = "• "
            para.runs[-1].text = trimmed


def _build_relevance_map(tailored: dict) -> dict[str, int]:
    """Build a mapping from bullet text to jd_relevance score."""
    relevance = {}
    for role in tailored.get("experience", []):
        for bullet in role.get("bullets_selected", []):
            text = bullet.get("text_final", "")
            score = bullet.get("jd_relevance", 5)  # default mid-range
            relevance[text] = score
    return relevance


def _trim_one_bullet(doc, relevance_map: dict[str, int] | None = None) -> bool:
    """Remove the least JD-relevant bullet from the role with the most bullets.

    If relevance_map is provided, picks the lowest-scored bullet from the
    largest group. Otherwise falls back to removing the last bullet.

    Returns True if a bullet was removed, False if no more can be trimmed.
    """
    bullet_groups = []
    current_group = []
    for para in doc.paragraphs:
        if para.text.startswith("• "):
            current_group.append(para)
        else:
            if current_group:
                bullet_groups.append(current_group)
                current_group = []
    if current_group:
        bullet_groups.append(current_group)

    if not bullet_groups:
        return False

    largest = max(bullet_groups, key=len)
    if len(largest) <= MIN_BULLETS_PER_ROLE:
        return False

    if relevance_map:
        # Remove the least JD-relevant bullet from this group
        victim = min(largest, key=lambda p: relevance_map.get(p.text.lstrip("• "), 5))
    else:
        victim = largest[-1]

    log.info("Trimming bullet for overflow (relevance=%d): '%s'",
             relevance_map.get(victim.text.lstrip("• "), -1) if relevance_map else -1,
             victim.text[:60])
    victim._p.getparent().remove(victim._p)
    return True


def _build_doc(tailored, bank):
    """Build a Document object with all resume sections."""
    doc = Document()

    for section in doc.sections:
        section.top_margin = MARGIN
        section.bottom_margin = MARGIN
        section.left_margin = MARGIN
        section.right_margin = MARGIN

    style = doc.styles['Normal']
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE
    style.paragraph_format.space_after = Pt(0)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.line_spacing = LINE_SPACING

    _add_contact_section(doc, bank.get("contact", {}))
    _add_summary_section(doc, tailored.get("summary_text_final", ""))
    _add_experience_section(doc, tailored, bank)
    _add_skills_section(doc, tailored, bank)
    _add_education_section(doc, bank)
    _add_projects_section(doc, tailored, bank)

    return doc


def generate_docx(tailored: dict, bank: dict, job: dict,
                  output_dir: str | Path | None = None,
                  keep_pdf: bool = False,
                  skip_pdf_check: bool = False) -> Path:
    """Generate a DOCX resume from tailored output.

    Page-fit strategy: render DOCX → PDF → check page count → trim if needed → repeat.
    PDF rendering (via Word/LibreOffice) is the layout source of truth.

    Args:
        tailored: Tailored resume dict from tailoring.py.
        bank: Loaded resume bank.
        job: Normalized job dict.
        output_dir: Directory to save the DOCX. Defaults to data/resumes/{today}.
        keep_pdf: If True, keep the final PDF alongside the DOCX.
        skip_pdf_check: If True, skip PDF rendering (for tests/environments without Word).

    Returns:
        Path to the generated DOCX file.
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "resumes" / date.today().isoformat()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = _build_doc(tailored, bank)

    # Step 1: Reflow bullets in orphan zone (76-110 chars → ≤75)
    _reflow_bullets(doc)

    # Log heuristic estimate for diagnostics
    est_lines = _estimate_content_lines(doc)
    log.info("Heuristic estimate: %.1f lines (diagnostic only)", est_lines)

    # Build JD relevance map for smart trimming
    relevance_map = _build_relevance_map(tailored)

    # Step 2: PDF render-measure-adjust loop
    filename = generate_resume_filename(bank, job)
    filepath = output_dir / filename
    trimmed_total = 0

    if skip_pdf_check:
        doc.save(str(filepath))
        log.info("Generated resume (PDF check skipped): %s", filepath)
        return filepath

    for pass_num in range(1, MAX_TRIM_PASSES + 2):
        doc.save(str(filepath))

        try:
            pdf_path = _render_to_pdf(filepath)
            pages = _count_pdf_pages(pdf_path)
        except Exception as e:
            log.warning("PDF rendering failed (%s), falling back to heuristic", e)
            pdf_path_candidate = filepath.with_suffix(".pdf")
            if pdf_path_candidate.exists():
                pdf_path_candidate.unlink()
            break

        log.info("PDF render pass %d: %d page(s), %d bullet(s) trimmed so far",
                 pass_num, pages, trimmed_total)

        if pages <= 1:
            if not keep_pdf:
                pdf_path.unlink(missing_ok=True)
            else:
                log.info("Kept PDF: %s", pdf_path)
            break

        # Clean up intermediate PDF before trimming
        pdf_path.unlink(missing_ok=True)

        if trimmed_total >= MAX_TRIM_PASSES:
            log.warning("Hit max trim passes (%d), resume still %d pages",
                        MAX_TRIM_PASSES, pages)
            break

        if not _trim_one_bullet(doc, relevance_map):
            log.warning("Cannot trim more bullets — resume still %d pages", pages)
            break

        trimmed_total += 1

    if trimmed_total:
        log.info("Trimmed %d bullet(s) to fit one page", trimmed_total)

    # Save tailored JSON sidecar for reuse/debugging
    import json
    json_path = filepath.with_suffix(".json")
    with open(json_path, "w") as f:
        json.dump(tailored, f, indent=2)
    log.info("Saved tailored JSON: %s", json_path)

    log.info("Generated resume: %s", filepath)
    return filepath
