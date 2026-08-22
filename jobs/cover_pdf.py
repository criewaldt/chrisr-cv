"""Render a cover letter as a PDF on the same letterhead as the resume.

Reuses the palette and profile links from resume/pdf.py so the two documents read
as one package rather than two unrelated files.
"""
from datetime import date
from html import escape
from io import BytesIO

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from resume.pdf import ACCENT, INK, INK_DARK, MUTED, PROFILE_LINKS, RULE

MARGIN = 0.9 * inch

STYLES = {
    'name': ParagraphStyle('name', fontName='Helvetica-Bold', fontSize=17, leading=21,
                           textColor=INK_DARK, spaceAfter=2),
    'contact': ParagraphStyle('contact', fontName='Helvetica', fontSize=8.5, leading=12,
                              textColor=MUTED, spaceAfter=2),
    'meta': ParagraphStyle('meta', fontName='Helvetica', fontSize=9.5, leading=14,
                           textColor=MUTED, spaceAfter=2),
    'salutation': ParagraphStyle('salutation', fontName='Helvetica', fontSize=10.5,
                                 leading=15, textColor=INK, spaceAfter=9),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10.5, leading=16,
                           textColor=INK, alignment=TA_JUSTIFY, spaceAfter=11),
    'signoff': ParagraphStyle('signoff', fontName='Helvetica', fontSize=10.5, leading=16,
                              textColor=INK, spaceBefore=6),
}


def _paragraphs(text):
    """Split on blank lines. Usually one block -- the prompt asks for a single one."""
    blocks, current = [], []
    for line in (text or '').replace('\r\n', '\n').split('\n'):
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(' '.join(current))
            current = []
    if current:
        blocks.append(' '.join(current))
    return blocks


def render_cover_letter_pdf(view, posting, body_text, applicant=None):
    """``view`` is a TailoredResumeView; ``posting`` supplies company and role."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=f'{view.name} - Cover Letter - {posting.company}',
        author=view.name or '', subject=f'Cover letter for {posting.title}',
    )

    separator = ' &nbsp;|&nbsp; '
    contact = separator.join(escape(x) for x in (view.email, view.phone) if x)
    links = separator.join(f'<a href="{url}" color="#434E5E">{escape(label)}</a>'
                           for label, url in PROFILE_LINKS)

    story = [Paragraph(escape(view.name or ''), STYLES['name'])]
    if contact:
        story.append(Paragraph(contact, STYLES['contact']))
    if links:
        story.append(Paragraph(links, STYLES['contact']))
    story += [
        HRFlowable(width='100%', thickness=0.75, color=RULE,
                   spaceBefore=8, spaceAfter=14),
        Paragraph(date.today().strftime('%B %-d, %Y'), STYLES['meta']),
        Spacer(1, 10),
        Paragraph(f'<b>{escape(posting.company or "")}</b>', STYLES['meta']),
        Paragraph(escape(f'Re: {posting.title}'), STYLES['meta']),
        Spacer(1, 16),
        Paragraph('Dear Hiring Team,', STYLES['salutation']),
    ]

    for block in _paragraphs(body_text) or ['']:
        story.append(Paragraph(escape(block), STYLES['body']))

    story += [
        Spacer(1, 10),
        Paragraph('Sincerely,', STYLES['signoff']),
        Spacer(1, 4),
        Paragraph(f'<b>{escape(view.name or "")}</b>', STYLES['signoff']),
    ]

    doc.build(story)
    return buffer.getvalue()
