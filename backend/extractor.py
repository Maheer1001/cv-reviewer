import io
import re
from typing import Dict, List, Optional, Tuple

import docx
import pymupdf as fitz

from backend.schemas import (
    ATSDetectedIssue,
    ContactDetails,
    DocumentDiagnostics,
    ExtractedBullet,
    ExtractedCV,
    ExtractedSection,
)


EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(
    r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{3,4})"
)
LINKEDIN_REGEX = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?", re.I)
GITHUB_REGEX = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_.-]+/?", re.I)
URL_REGEX = re.compile(
    r"(?:https?://|www\.)[a-zA-Z0-9./?=_-]+|[a-zA-Z0-9-]+\.(?:dev|io|me|co\.uk|com|org)/[a-zA-Z0-9./?=_-]*",
    re.I,
)

BULLET_PREFIX_REGEX = re.compile(r"^\s*(?:[•●▪▫◦‣⁃\-–—*›»]|\(\d+\)|\d+\.)\s+")

STANDARD_SECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "summary",
        re.compile(
            r"^(?:personal\s+profile|professional\s+profile|professional\s+summary|executive\s+summary|summary|profile|objective|career\s+objective|about\s+me)$",
            re.I,
        ),
    ),
    (
        "experience",
        re.compile(
            r"^(?:work\s+experience|professional\s+experience|employment\s+history|employment|experience|career\s+history|internships?|industrial\s+placements?|relevant\s+experience|"
            r"relevant\s+work\s+experience|placements?|research\s+experience|research\s+positions|"
            r"(?:laboratory|lab)\s+experience|industry\s+experience|professional\s+experience|"
            r"open[\s-]source(?:\s+(?:work|contributions?|experience))?|freelance(?:\s+(?:work|experience))?)$",
            re.I,
        ),
    ),
    (
        "projects",
        re.compile(
            r"^(?:projects?|technical\s+projects?|personal\s+projects?|academic\s+projects?|selected\s+projects?|key\s+projects?|open[\s-]?source\s+projects?|"
            r"research|research\s+projects?|dissertation|thesis|(?:undergraduate|masters?|mphys|msci|meng|msc|bsc|beng|phd)\s+(?:dissertation|project|thesis)|"
            r"final[\s-]year\s+projects?|capstone\s+projects?|design\s+projects?|engineering\s+projects?|side\s+projects?|"
            r"hackathons?|competitions?|robotics?(?:\s+projects?)?)$",
            re.I,
        ),
    ),
    (
        "education",
        re.compile(
            r"^(?:education|academic\s+background|academic\s+qualifications|qualifications|education\s+&\s+training|education\s+and\s+qualifications)$",
            re.I,
        ),
    ),
    (
        "skills",
        re.compile(
            r"^(?:technical\s+skills|skills|core\s+skills|key\s+skills|skills\s+&\s+technologies|technologies|competencies|technical\s+proficiencies|programming\s+languages\s*&\s*tools|"
            r"(?:laboratory|lab|research|professional|computing|it|software|analytical|security|cloud|data)\s+skills|"
            r"tools\s*(?:&|and)\s*(?:technologies|techniques)|technologies\s*(?:&|and)\s*tools)$",
            re.I,
        ),
    ),
    (
        "certifications",
        re.compile(
            r"^(?:certifications?|licen[cs]es\s*&\s*certifications?|professional\s+certifications?|courses\s*&\s*certifications?|training\s*&\s*certifications?|"
            r"professional\s+(?:qualifications|certifications?|development)|accreditations?|training\s*(?:&|and)\s*certifications?|courses)$",
            re.I,
        ),
    ),
    (
        "additional",
        re.compile(
            r"^(?:additional\s+information|awards?\s*(?:&\s*honours)?|honours?\s*&\s*awards?|publications?|volunteering|leadership|extracurricular\s+activities|interests|hobbies|languages|"
            r"publications\s*(?:&|and)\s*(?:presentations|talks)|presentations|talks|conference\s+(?:talks|papers)|open[\s-]source\s+contributions?|"
            r"hackathons?|competitions?|prizes?|awards?\s*(?:&|and)\s*prizes|achievements|positions\s+of\s+responsibility|activities|referees|references)$",
            re.I,
        ),
    ),
]

AMBIGUOUS_SECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("summary", re.compile(r"^(?:who\s+i\s+am|my\s+story|introduction|the\s+pitch|what\s+i\s+bring)$", re.I)),
    ("experience", re.compile(r"^(?:where\s+i'?ve\s+been|my\s+journey|career\s+adventures|work\s+chronicles)$", re.I)),
    ("skills", re.compile(r"^(?:my\s+arsenal|tech\s+arsenal|weaponry|toolbox|superpowers|what\s+i\s+know)$", re.I)),
    ("projects", re.compile(r"^(?:things\s+i'?ve\s+built|cool\s+stuff|creations|lab\s+work|sandbox)$", re.I)),
]


class DocumentExtractionError(Exception):
    """Raised when an uploaded CV cannot be parsed."""


def _n(count: int, singular: str, plural: str = "") -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def extract_cv_from_bytes(filename: str, content: bytes) -> ExtractedCV:
    """Extract text, structural layout, sections, bullets, and ATS diagnostics from PDF, DOCX, or TXT."""
    if not content or len(content) == 0:
        raise DocumentExtractionError("The uploaded file is empty (0 bytes). Please upload a valid PDF or DOCX CV.")

    lower_name = (filename or "uploaded_cv").lower()
    if lower_name.endswith(".pdf"):
        return _extract_from_pdf(filename, content)
    elif lower_name.endswith(".docx"):
        return _extract_from_docx(filename, content)
    elif lower_name.endswith(".txt"):
        return _extract_from_txt(filename, content)
    else:
        raise DocumentExtractionError(
            f"Unsupported file format for '{filename}'. Please upload a CV in PDF (.pdf) or Word (.docx) format."
        )


def _extract_from_pdf(filename: str, content: bytes) -> ExtractedCV:
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise DocumentExtractionError(
            f"Failed to open PDF file '{filename}'. The file appears corrupted or is not a valid PDF ({exc})."
        ) from exc

    if doc.page_count == 0:
        raise DocumentExtractionError(f"PDF '{filename}' contains 0 pages.")

    raw_pages_text: List[str] = []
    header_footer_texts: List[str] = []
    links: List[str] = []
    reading_order_anomalies: List[str] = []
    has_multi_column = False
    has_tables = False
    table_count = 0
    has_shapes = False

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        page_rect = page.rect
        page_width = max(page_rect.width, 1.0)
        page_height = max(page_rect.height, 1.0)

        # Extract embedded URI links
        for link in page.get_links():
            uri = link.get("uri")
            if uri and uri not in links:
                links.append(uri)

        # Check drawings/vector shapes that might indicate text boxes or skill bars
        try:
            drawings = page.get_drawings()
            if len(drawings) > 35:
                has_shapes = True
        except Exception:
            pass

        # Check tables if find_tables is supported
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                has_tables = True
                table_count += len(tabs.tables)
        except Exception:
            pass

        blocks = page.get_text("blocks")
        text_blocks = [b for b in blocks if len(b) >= 7 and b[6] == 0 and str(b[4]).strip()]

        # Inspect header/footer margin regions (top 6% or bottom 6%)
        for b in text_blocks:
            x0, y0, x1, y1, b_text = b[0], b[1], b[2], b[3], str(b[4]).strip()
            if y1 <= page_height * 0.065 or y0 >= page_height * 0.935:
                if len(b_text) > 3 and not re.match(r"^(?:page\s*)?\d+(?:\s*of\s*\d+)?$", b_text, re.I):
                    header_footer_texts.append(b_text.replace("\n", " "))

        # Detect multi-column layout by checking if narrow blocks overlap vertically on left and right halves
        left_blocks = [
            b for b in text_blocks if b[0] < page_width * 0.35 and (b[2] - b[0]) < page_width * 0.58
        ]
        right_blocks = [
            b for b in text_blocks if b[0] >= page_width * 0.40 and (b[2] - b[0]) < page_width * 0.58
        ]
        overlap_pairs = 0
        for lb in left_blocks:
            for rb in right_blocks:
                vertical_overlap = min(lb[3], rb[3]) - max(lb[1], rb[1])
                if vertical_overlap > 8:
                    overlap_pairs += 1
                    break
        if overlap_pairs >= 2:
            has_multi_column = True
            reading_order_anomalies.append(
                f"Page {page_idx + 1} uses a multi-column layout ({overlap_pairs} vertically overlapping column blocks detected). "
                "Linear ATS parsers frequently interleave left and right column lines out of order."
            )

        # Check non-monotonic vertical jumps in natural block order
        prev_y0 = -1.0
        upward_jumps = 0
        for b in text_blocks:
            if prev_y0 > 0 and b[1] < prev_y0 - 40:
                upward_jumps += 1
            prev_y0 = b[1]
        if upward_jumps >= 2 and not has_multi_column:
            reading_order_anomalies.append(
                f"Page {page_idx + 1} exhibits non-linear text block ordering ({upward_jumps} upward coordinate jumps), "
                "which can scramble section attribution during automated parsing."
            )

        page_text = page.get_text("text")
        raw_pages_text.append(page_text)

    page_count = doc.page_count
    doc.close()

    full_text = "\n".join(raw_pages_text).strip()
    diagnostics = DocumentDiagnostics(
        filename=filename,
        file_format="pdf",
        file_size_bytes=len(content),
        page_count=page_count,
        has_tables=has_tables,
        table_count=table_count,
        has_multi_column_layout=has_multi_column,
        has_text_boxes_or_shapes=has_shapes,
        has_header_footer_content=len(header_footer_texts) > 0,
        header_footer_text=header_footer_texts[:6],
        links_extracted=links,
        reading_order_anomalies=reading_order_anomalies,
    )

    return _build_extracted_cv_from_text(full_text, diagnostics)


def _extract_from_docx(filename: str, content: bytes) -> ExtractedCV:
    try:
        doc = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError(
            f"Failed to parse DOCX file '{filename}'. The file appears corrupted or is not a valid Word document ({exc})."
        ) from exc

    lines: List[str] = []
    header_footer_texts: List[str] = []
    links: List[str] = []
    reading_order_anomalies: List[str] = []
    heading_styles_count = 0

    # Extract hyperlinks from document relationships
    try:
        for rel in doc.part.rels.values():
            if "hyperlink" in rel.reltype and getattr(rel, "target_ref", None):
                target = str(rel.target_ref)
                if target not in links:
                    links.append(target)
    except Exception:
        pass

    # Inspect headers and footers
    for section in doc.sections:
        for hf in (section.header, section.footer):
            if hf and not hf.is_linked_to_previous:
                for p in hf.paragraphs:
                    txt = p.text.strip()
                    if txt and txt not in header_footer_texts:
                        header_footer_texts.append(txt)
                for tbl in hf.tables:
                    for row in tbl.rows:
                        row_txt = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                        if row_txt and row_txt not in header_footer_texts:
                            header_footer_texts.append(row_txt)

    # Check XML for textboxes (w:txbxContent)
    textbox_texts: List[str] = []
    has_textboxes = False
    try:
        xml_body = doc.element.body
        txbx_nodes = xml_body.xpath(".//*[local-name()='txbxContent']")
        if txbx_nodes:
            has_textboxes = True
            for node in txbx_nodes:
                texts = node.xpath(".//*[local-name()='t']/text()")
                joined = "".join(texts).strip()
                if joined:
                    textbox_texts.append(joined)
            reading_order_anomalies.append(
                f"Detected {_n(len(txbx_nodes), 'floating Word text box', 'floating Word text boxes')} (w:txbxContent). "
                "Many legacy ATS parsers completely ignore text inside floating drawing layers."
            )
    except Exception:
        pass

    # Extract paragraphs
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style_name = (p.style.name if p.style else "").lower()
        if "heading" in style_name:
            heading_styles_count += 1
        # Check if paragraph is a list item in Word XML
        is_list_para = False
        try:
            if "list" in style_name or p._p.xpath("./*[local-name()='pPr']/*[local-name()='numPr']"):
                is_list_para = True
        except Exception:
            pass
        if is_list_para and not BULLET_PREFIX_REGEX.match(txt):
            lines.append(f"• {txt}")
        else:
            lines.append(txt)

    # Extract tables
    table_count = len(doc.tables)
    has_tables = table_count > 0
    has_multi_column_table = False
    for tbl in doc.tables:
        col_count = len(tbl.columns) if tbl.columns else 0
        if col_count >= 2:
            has_multi_column_table = True
        for row in tbl.rows:
            seen_cells = []
            for cell in row.cells:
                c_txt = cell.text.strip()
                if c_txt and c_txt not in seen_cells:
                    seen_cells.append(c_txt)
            if seen_cells:
                for c_block in seen_cells:
                    for subline in c_block.splitlines():
                        if subline.strip():
                            lines.append(subline.strip())

    if has_multi_column_table:
        reading_order_anomalies.append(
            f"Document uses {_n(table_count, 'Word table')} with multiple columns to structure content. "
            "ATS parsers often flatten table cells row-by-row rather than column-by-column."
        )

    for tb_txt in textbox_texts:
        if tb_txt not in "\n".join(lines):
            lines.append(tb_txt)

    # Also include header/footer text at top if it wasn't in body so we can still see it, while flagging it
    full_body_text = "\n".join(lines).strip()
    if header_footer_texts:
        missing_hf = [hf for hf in header_footer_texts if hf not in full_body_text]
        if missing_hf:
            full_text = "\n".join(missing_hf) + "\n" + full_body_text
        else:
            full_text = full_body_text
    else:
        full_text = full_body_text

    estimated_pages = max(1, int(round(len(full_text.split()) / 450.0))) if full_text else 1

    diagnostics = DocumentDiagnostics(
        filename=filename,
        file_format="docx",
        file_size_bytes=len(content),
        page_count=estimated_pages,
        has_tables=has_tables,
        table_count=table_count,
        has_multi_column_layout=has_multi_column_table,
        has_text_boxes_or_shapes=has_textboxes,
        has_header_footer_content=len(header_footer_texts) > 0,
        header_footer_text=header_footer_texts[:6],
        links_extracted=links,
        reading_order_anomalies=reading_order_anomalies,
    )

    return _build_extracted_cv_from_text(full_text, diagnostics)


def _extract_from_txt(filename: str, content: bytes) -> ExtractedCV:
    try:
        full_text = content.decode("utf-8")
    except UnicodeDecodeError:
        full_text = content.decode("latin-1", errors="replace")

    full_text = full_text.strip()
    estimated_pages = max(1, int(round(len(full_text.split()) / 450.0))) if full_text else 1
    diagnostics = DocumentDiagnostics(
        filename=filename,
        file_format="txt",
        file_size_bytes=len(content),
        page_count=estimated_pages,
    )
    return _build_extracted_cv_from_text(full_text, diagnostics)


def _classify_heading(line: str) -> Optional[Tuple[str, bool]]:
    """
    Determine if a line is a CV section heading.
    Returns (normalized_section_type, is_ambiguous) or None.
    """
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 55:
        return None
    if BULLET_PREFIX_REGEX.match(cleaned):
        return None
    # Strip trailing colon or decorative dashes
    stripped = re.sub(r"^[\s\-–—=_#*]+|[\s\-–—=_#*:]+$", "", cleaned).strip()
    if not stripped or len(stripped) < 3:
        return None

    # Avoid classifying lines with dates or emails as section headings
    if EMAIL_REGEX.search(stripped) or re.search(r"\b(?:19|20)\d{2}\b", stripped):
        return None

    for norm_type, pattern in STANDARD_SECTION_PATTERNS:
        if pattern.match(stripped):
            return (norm_type, False)

    for norm_type, pattern in AMBIGUOUS_SECTION_PATTERNS:
        if pattern.match(stripped):
            return (norm_type, True)

    return None


def _extract_contact_details(
    raw_text: str,
    top_lines: List[str],
    diagnostics: DocumentDiagnostics,
) -> ContactDetails:
    header_joined = "\n".join(top_lines[:10])
    search_space = header_joined + "\n" + "\n".join(diagnostics.header_footer_text)

    email_match = EMAIL_REGEX.search(search_space) or EMAIL_REGEX.search(raw_text)
    email = email_match.group(0) if email_match else None

    # Phone extraction (avoid matching 4-digit year ranges like 2021 - 2024)
    phone = None
    for candidate in PHONE_REGEX.findall(search_space):
        cleaned_cand = candidate.strip()
        digits = re.sub(r"\D", "", cleaned_cand)
        if 10 <= len(digits) <= 14 and not re.match(r"^(?:19|20)\d{2}\D+(?:19|20)\d{2}$", cleaned_cand):
            phone = cleaned_cand
            break

    linkedin_match = LINKEDIN_REGEX.search(raw_text)
    linkedin = linkedin_match.group(0) if linkedin_match else None

    github_match = GITHUB_REGEX.search(raw_text)
    github = github_match.group(0) if github_match else None

    for link in diagnostics.links_extracted:
        if not linkedin and "linkedin.com" in link.lower():
            linkedin = link
        if not github and "github.com" in link.lower():
            github = link

    portfolio_links: List[str] = []
    for match in URL_REGEX.findall(raw_text):
        low = match.lower()
        if "linkedin.com" not in low and "github.com" not in low and "@" not in low:
            if match not in portfolio_links:
                portfolio_links.append(match)

    # Infer candidate name from first non-empty line that isn't a heading, email, or phone
    name = None
    for line in top_lines[:5]:
        cleaned = line.strip()
        if not cleaned:
            continue
        if EMAIL_REGEX.search(cleaned):
            # Could be "Name | email@domain.com | phone"
            parts = [p.strip() for p in re.split(r"[|•·]", cleaned) if p.strip()]
            if parts and not EMAIL_REGEX.search(parts[0]) and len(parts[0].split()) <= 5:
                name = parts[0]
                break
            continue
        if _classify_heading(cleaned):
            continue
        if len(cleaned.split()) <= 5 and len(cleaned) <= 45:
            name = re.sub(r"[|•].*$", "", cleaned).strip()
            break

    # Infer location from common UK/international location indicators in top lines
    location = None
    loc_regex = re.compile(
        r"\b(London|Manchester|Birmingham|Edinburgh|Glasgow|Bristol|Leeds|Cambridge|Oxford|Belfast|Cardiff|Reading|Remote|United Kingdom|UK|New York|San Francisco|Dublin|Berlin|Toronto)\b(?:,\s*[A-Za-z\s]+)?",
        re.I,
    )
    loc_match = loc_regex.search(header_joined)
    if loc_match:
        location = loc_match.group(0).strip()

    # Check if email or phone is trapped in header/footer
    hf_blob = " ".join(diagnostics.header_footer_text)
    found_in_hf = False
    if hf_blob:
        if (email and email in hf_blob) or (phone and phone in hf_blob):
            found_in_hf = True

    missing_fields: List[str] = []
    if not email:
        missing_fields.append("Email address")
    if not phone:
        missing_fields.append("Telephone number")
    if not linkedin and not github and not portfolio_links:
        missing_fields.append("Professional profile or portfolio link (LinkedIn / GitHub)")

    return ContactDetails(
        name=name or "Candidate",
        email=email,
        phone=phone,
        location=location,
        linkedin=linkedin,
        github=github,
        portfolio_links=portfolio_links,
        found_in_header_or_footer=found_in_hf,
        missing_critical_fields=missing_fields,
    )


def _is_entry_header(line: str, section_type: str) -> bool:
    """Detect if a non-bullet line inside Experience, Projects, or Education is a role/project/degree title line."""
    if section_type not in ("experience", "projects", "education"):
        return False
    if len(line) > 115:
        return False
    # Contains date ranges, pipe separators, or role/degree patterns
    if re.search(r"\b(?:19|20)\d{2}\b|\bPresent\b|\bCurrent\b|\|", line, re.I):
        return True
    if section_type == "projects" and len(line.split()) <= 10 and not line.endswith("."):
        return True
    return False


def _build_extracted_cv_from_text(full_text: str, diagnostics: DocumentDiagnostics) -> ExtractedCV:
    words = full_text.split()
    diagnostics.word_count = len(words)
    diagnostics.char_count = len(full_text)

    if diagnostics.word_count < 25:
        diagnostics.extraction_complete = False
        diagnostics.extraction_warnings.append(
            f"Only {diagnostics.word_count} words could be extracted from '{diagnostics.filename}'. "
            "The document may be a scanned image without an OCR text layer, or nearly empty. "
            "Any review of this incomplete text cannot be treated as comprehensive."
        )
    if diagnostics.word_count == 0:
        raise DocumentExtractionError(
            f"No readable text could be extracted from '{diagnostics.filename}'. "
            "Ensure the document contains selectable text rather than scanned images."
        )

    raw_lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    contact = _extract_contact_details(full_text, raw_lines[:12], diagnostics)

    sections: List[ExtractedSection] = []
    all_bullets: List[ExtractedBullet] = []
    ambiguous_headings: List[str] = []

    current_section = ExtractedSection(
        section_id="sec_0",
        title="Contact & Header",
        normalized_type="contact",
        raw_lines=[],
        items=[],
    )
    sections.append(current_section)

    sec_counter = 0
    bullet_counter = 0
    current_entry_title: Optional[str] = None

    for line_idx, line in enumerate(raw_lines):
        heading_Check = _classify_heading(line)
        if heading_Check is not None:
            norm_type, is_ambiguous = heading_Check
            if is_ambiguous:
                ambiguous_headings.append(line)
                diagnostics.standard_headings_used = False
            sec_counter += 1
            current_entry_title = None
            current_section = ExtractedSection(
                section_id=f"sec_{sec_counter}",
                title=re.sub(r"^[\s\-–—=_#*]+|[\s\-–—=_#*:]+$", "", line).strip(),
                normalized_type=norm_type,  # type: ignore[arg-type]
                raw_lines=[],
                items=[],
            )
            sections.append(current_section)
            continue

        current_section.raw_lines.append(line)

        is_bul = bool(BULLET_PREFIX_REGEX.match(line))
        clean_text = BULLET_PREFIX_REGEX.sub("", line).strip() if is_bul else line.strip()

        if not is_bul and _is_entry_header(clean_text, current_section.normalized_type):
            current_entry_title = clean_text
            bullet_counter += 1
            eb = ExtractedBullet(
                bullet_id=f"item_{bullet_counter}",
                section_name=current_section.title,
                entry_title=current_entry_title,
                text=clean_text,
                is_bullet=False,
                line_index=line_idx,
            )
            current_section.items.append(eb)
            continue

        # In contact section, skip pure name/email header lines from being treated as editable experience bullets
        if current_section.normalized_type == "contact" and line_idx < 4 and len(clean_text.split()) <= 12:
            bullet_counter += 1
            eb = ExtractedBullet(
                bullet_id=f"item_{bullet_counter}",
                section_name=current_section.title,
                entry_title=None,
                text=clean_text,
                is_bullet=False,
                line_index=line_idx,
            )
            current_section.items.append(eb)
            continue

        # If a candidate wrote a long unstructured CV without standard headings after line 4, move to summary/experience
        if current_section.normalized_type == "contact" and line_idx >= 4:
            sec_counter += 1
            current_section = ExtractedSection(
                section_id=f"sec_{sec_counter}",
                title="Unlabelled Content / Experience",
                normalized_type="experience" if is_bul else "summary",
                raw_lines=[line],
                items=[],
            )
            sections.append(current_section)
            diagnostics.standard_headings_used = False
            ambiguous_headings.append("(Missing explicit section heading)")

        bullet_counter += 1
        eb = ExtractedBullet(
            bullet_id=f"item_{bullet_counter}",
            section_name=current_section.title,
            entry_title=current_entry_title,
            text=clean_text,
            is_bullet=is_bul or current_section.normalized_type in ("experience", "projects"),
            line_index=line_idx,
        )
        current_section.items.append(eb)
        if eb.is_bullet or current_section.normalized_type in ("summary", "skills", "education", "certifications"):
            all_bullets.append(eb)

    # Filter out empty sections
    sections = [s for s in sections if s.raw_lines or s.items]
    diagnostics.section_count = len(sections)
    diagnostics.bullet_count = sum(1 for b in all_bullets if b.is_bullet)
    diagnostics.ambiguous_headings = ambiguous_headings

    # Populate ATS detected issues (distinguishing verified document issues from general best practices)
    diagnostics.ats_issues = _build_ats_issues(diagnostics, contact, sections)

    return ExtractedCV(
        raw_text=full_text,
        contact=contact,
        sections=sections,
        all_bullets=all_bullets,
        diagnostics=diagnostics,
    )


def _build_ats_issues(
    diagnostics: DocumentDiagnostics,
    contact: ContactDetails,
    sections: List[ExtractedSection],
) -> List[ATSDetectedIssue]:
    issues: List[ATSDetectedIssue] = []
    idx = 0

    if not diagnostics.extraction_complete:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high",
                issue_type="verified_document_issue",
                title="Incomplete Text Extraction / Low Text Density",
                description="The uploaded file yielded fewer than 25 extractable words.",
                evidence=f"Extracted only {diagnostics.word_count} words across {_n(diagnostics.page_count, 'page')}.",
                remediation="Ensure the CV is exported directly from a word processor as selectable text rather than scanned images or flattened graphics.",
            )
        )

    if diagnostics.has_multi_column_layout:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high",
                issue_type="verified_document_issue",
                title="Multi-Column Layout Detected",
                description="Content is arranged in side-by-side columns or multi-column tables.",
                evidence="; ".join(diagnostics.reading_order_anomalies)
                or "Side-by-side column coordinates detected in document layout.",
                remediation="Switch to a single-column top-to-bottom layout so ATS text extractors do not merge adjacent lines across columns.",
            )
        )

    if diagnostics.has_tables:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="medium",
                issue_type="verified_document_issue",
                title=f"Tables Detected ({_n(diagnostics.table_count, 'table')})",
                description="Tabular structures were detected in the document.",
                evidence=f"Inspector found {_n(diagnostics.table_count, 'table structure')} in '{diagnostics.filename}'.",
                remediation="Replace layout tables and skill grids with standard linear paragraphs and bulleted lists.",
            )
        )

    if diagnostics.has_text_boxes_or_shapes:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high",
                issue_type="verified_document_issue",
                title="Floating Text Boxes or Heavy Vector Graphics Detected",
                description="Document contains floating text boxes (w:txbxContent) or excessive vector shapes (often used for visual skill bars).",
                evidence="Detected floating drawing elements or text boxes in document structure.",
                remediation="Move all text into the main document body flow and remove graphical skill progress bars.",
            )
        )

    if contact.found_in_header_or_footer or diagnostics.has_header_footer_content:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high" if contact.found_in_header_or_footer else "medium",
                issue_type="verified_document_issue",
                title="Content Placed Inside Document Header or Footer",
                description=(
                    "Critical contact details were detected inside the document header/footer margin."
                    if contact.found_in_header_or_footer
                    else "Text was found in the document header/footer margin."
                ),
                evidence=f"Header/footer text: {' | '.join(diagnostics.header_footer_text[:2])}",
                remediation="Place your name, email, telephone number, and links in the main body of Page 1 rather than inside Word/PDF header/footer containers.",
            )
        )

    if contact.missing_critical_fields:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high",
                issue_type="verified_document_issue",
                title="Missing or Unparsable Contact Details",
                description="Essential contact information could not be extracted from the CV.",
                evidence=f"Missing fields: {', '.join(contact.missing_critical_fields)}.",
                remediation="Include a clear plain-text email address, telephone number, and LinkedIn/GitHub URL at the top of the CV.",
            )
        )

    if diagnostics.ambiguous_headings:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="medium",
                issue_type="verified_document_issue",
                title="Non-Standard or Missing Section Headings",
                description="Unconventional or missing section headings can prevent automated parsers from categorising work history and education accurately.",
                evidence=f"Detected {'a non-standard heading' if len(diagnostics.ambiguous_headings) == 1 else 'non-standard headings'}: {', '.join(diagnostics.ambiguous_headings)}",
                remediation="Use standard, unambiguous headings: 'Professional Summary', 'Work Experience', 'Projects', 'Technical Skills', and 'Education'.",
            )
        )

    section_types = {s.normalized_type for s in sections}
    if "experience" not in section_types and "projects" not in section_types:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="high",
                issue_type="verified_document_issue",
                title="No Clearly Recognised Experience or Projects Section",
                description="Neither a 'Work Experience' nor a 'Projects' section was identified under standard headings.",
                evidence=f"Detected section types: {', '.join(sorted(section_types))}",
                remediation="Add explicit 'Work Experience' and/or 'Projects' section headings so both parsers and recruiters can locate your track record immediately.",
            )
        )

    if diagnostics.word_count > 1100 or diagnostics.page_count > 2:
        idx += 1
        issues.append(
            ATSDetectedIssue(
                issue_id=f"ats_{idx}",
                severity="low",
                issue_type="verified_document_issue",
                title="Excessive Document Length",
                description=f"The CV spans {_n(diagnostics.page_count, 'page')} and {diagnostics.word_count} words.",
                evidence=f"{diagnostics.word_count} words across {_n(diagnostics.page_count, 'page')}.",
                remediation="Unless applying for an academic or senior executive post, condense the CV to 1–2 tightly edited pages (typically 450–850 words).",
            )
        )

    # Always include transparent general ATS best practice guidance distinguished from verified issues
    idx += 1
    issues.append(
        ATSDetectedIssue(
            issue_id=f"ats_{idx}",
            severity="info",
            issue_type="general_best_practice",
            title="ATS Parsing vs Employer Ranking Reality Check",
            description=(
                "No external tool can truthfully claim a CV has 'passed' or 'failed' every employer's ATS, because "
                "systems (Workday, Greenhouse, Lever, Taleo) configure custom knockout questions and recruiter filters differently."
            ),
            evidence="General recruitment platform guidance (not a defect in your file).",
            remediation="Focus on clean single-column structure, standard section titles, consistent 'Month YYYY – Month YYYY' date formats, and natural evidence-backed terminology rather than keyword stuffing.",
        )
    )

    return issues
