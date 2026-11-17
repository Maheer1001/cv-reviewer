import io
from typing import List

from docx import Document
from docx.shared import Pt, RGBColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.editing import placeholders_in, render_working_cv
from backend.schemas import SessionState, WorkingCV


def _blocks(working: WorkingCV) -> List[tuple[str, List[str], List[str]]]:
    """Return (section title, plain lines, bullet lines) for visible content."""
    blocks = []
    for section in working.sections:
        visible = [entry for entry in section.entries if not entry.is_deleted and entry.current_text.strip()]
        if not visible:
            continue
        plain = [entry.current_text for entry in visible if not entry.is_bullet]
        bullets = [entry.current_text for entry in visible if entry.is_bullet]
        blocks.append((section.title, plain, bullets))
    return blocks


def export_docx(session: SessionState) -> bytes:
    working = session.working_cv
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    contact = working.contact
    document.add_heading(contact.name or "Curriculum Vitae", level=0)
    bits = [bit for bit in (contact.email, contact.phone, contact.location, contact.linkedin, contact.github) if bit]
    if bits:
        paragraph = document.add_paragraph(" | ".join(bits))
        paragraph.runs[0].font.color.rgb = RGBColor(0x33, 0x3A, 0x42)
        paragraph.runs[0].font.size = Pt(10)
    for title, plain, bullets in _blocks(working):
        if title.lower().startswith("contact"):
            continue
        document.add_heading(title, level=1)
        for line in plain:
            document.add_paragraph(line)
        for line in bullets:
            document.add_paragraph(line, style="List Bullet")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def export_pdf(session: SessionState) -> bytes:
    working = session.working_cv
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=working.contact.name or "Revised CV",
    )
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Heading1"], fontName="Times-Bold", fontSize=16, spaceAfter=4)
    meta_style = ParagraphStyle("Meta", parent=styles["Normal"], fontName="Times-Roman", fontSize=9, textColor="#333A42", spaceAfter=8)
    heading = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Times-Bold", fontSize=12, spaceBefore=8, spaceAfter=3)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontName="Times-Roman", fontSize=10.5, leading=14, spaceAfter=2)
    bullet = ParagraphStyle("BulletBody", parent=body, leftIndent=12, bulletIndent=0, spaceAfter=2)
    story = [Paragraph(_xml(working.contact.name or "Curriculum Vitae"), name_style)]
    bits = [bit for bit in (working.contact.email, working.contact.phone, working.contact.location, working.contact.linkedin, working.contact.github) if bit]
    if bits:
        story.append(Paragraph(_xml(" | ".join(bits)), meta_style))
    for title, plain, bullets in _blocks(working):
        if title.lower().startswith("contact"):
            continue
        story.append(Paragraph(_xml(title), heading))
        for line in plain:
            story.append(Paragraph(_xml(line), body))
        for line in bullets:
            story.append(Paragraph("• " + _xml(line), bullet))
        story.append(Spacer(1, 4))
    document.build(story)
    return buffer.getvalue()


def export_change_summary(session: SessionState) -> str:
    lines = [
        "CV change summary",
        "This file lists decisions recorded in the session. The revised CV is generated from the working copy, not from a separate model draft.",
        "",
    ]
    for event in session.working_cv.change_history:
        lines.append(f"- {event.timestamp} {event.action_taken} in {event.section_name}")
        if event.before_text:
            lines.append(f"  Before: {event.before_text}")
        if event.after_text:
            lines.append(f"  After: {event.after_text}")
    lines.append("")
    lines.append("Recommendation decisions")
    for rec in session.initial_report.recommendations:
        lines.append(f"- [{rec.status}] {rec.action} {rec.rec_id}: {(rec.original_text or rec.suggested_text)[:160]}")
    flags = placeholders_in(session.working_cv)
    if flags:
        lines.append("")
        lines.append("Unresolved placeholders still in the working CV")
        lines.extend(f"- {flag}" for flag in flags)
    lines.append("")
    lines.append(render_working_cv(session.working_cv))
    return "\n".join(lines)


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
