"""Render the resume stored in the database as a downloadable PDF.

The document auto-fits a page budget: it is built at full size first, and if it
runs long the typography is scaled down a step at a time until it fits (or the
minimum readable size is reached).
"""
from html import escape
from io import BytesIO

from bs4 import BeautifulSoup, NavigableString

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Matches the .resume-header background in assets/css/pillar-1.css
HEADER_BG = colors.HexColor('#434E5E')
ACCENT = colors.HexColor('#434E5E')
MUTED = colors.HexColor('#6c757d')
RULE = colors.HexColor('#d4d9e0')
INK = colors.HexColor('#3f4650')
INK_DARK = colors.HexColor('#2f3742')

PAGE_WIDTH, PAGE_HEIGHT = LETTER
BASE_MARGIN = 0.65 * inch
BASE_BANNER_HEIGHT = 1.62 * inch

# Mirrors the profile links in chrisr/templates/index.html. Keep the two in sync;
# move them onto the Resume model if they ever need to differ per resume.
PROFILE_LINKS = (
    ('chrisriewaldt.com', 'https://chrisriewaldt.com'),
    ('linkedin.com/in/christopher-riewaldt-a21a531b',
     'https://www.linkedin.com/in/christopher-riewaldt-a21a531b'),
    ('github.com/criewaldt', 'https://github.com/criewaldt'),
)

DEFAULT_MAX_PAGES = 2
# Tried in order until the document fits the page budget. The last step keeps
# body text at ~7.8pt, which is about as small as a resume should go.
SCALE_STEPS = (1.0, 0.97, 0.94, 0.91, 0.88, 0.85, 0.82)

# Same category labels the web template uses, in the same order
SKILL_CATEGORIES = [
    ('web', 'Web Development'),
    ('language', 'Languages'),
    ('cloud', 'Cloud & DevOps'),
    ('ai', 'AI & ML'),
    ('methodology', 'Methodologies'),
]

# name -> (font, size, leading, color, extra ParagraphStyle kwargs)
STYLE_SPECS = {
    'name': ('Helvetica-Bold', 22, 26, colors.white, {'spaceAfter': 2}),
    'title': ('Helvetica', 12, 16, colors.Color(1, 1, 1, 0.85), {'spaceAfter': 6}),
    'contact': ('Helvetica', 9, 13, colors.Color(1, 1, 1, 0.75), {}),
    'section': ('Helvetica-Bold', 11, 14, ACCENT, {'spaceBefore': 4, 'spaceAfter': 4}),
    'body': ('Helvetica', 9.5, 13.5, INK, {'alignment': TA_JUSTIFY, 'spaceAfter': 4}),
    'bullet': ('Helvetica', 9.5, 13.5, INK, {'leftIndent': 12, 'bulletIndent': 2, 'spaceAfter': 2}),
    'job': ('Helvetica-Bold', 10.5, 14, INK_DARK, {}),
    'company': ('Helvetica-Bold', 10.5, 14, ACCENT, {'alignment': 2}),
    'meta': ('Helvetica-Oblique', 8.5, 12, MUTED, {'spaceAfter': 3}),
    'skill_cat': ('Helvetica-Bold', 9, 12, INK_DARK, {}),
    'skill_list': ('Helvetica', 9, 12.5, INK, {'spaceAfter': 4}),
    'entry': ('Helvetica-Bold', 9.5, 13, INK_DARK, {}),
    'entry_meta': ('Helvetica', 9, 12.5, MUTED, {'spaceAfter': 5}),
    'footer': ('Helvetica', 7.5, 10, MUTED, {}),
}

# ParagraphStyle measurements that scale with the rest of the type
SCALED_STYLE_KWARGS = ('spaceBefore', 'spaceAfter', 'leftIndent', 'bulletIndent')


class Layout:
    """Page geometry and typography for one render attempt."""

    def __init__(self, scale):
        self.scale = scale
        self.margin = max(0.5 * inch, BASE_MARGIN * scale)
        self.banner_height = max(1.25 * inch, BASE_BANNER_HEIGHT * scale)
        self.content_width = PAGE_WIDTH - 2 * self.margin
        self.styles = {
            name: ParagraphStyle(
                name,
                fontName=font,
                fontSize=size * scale,
                leading=leading * scale,
                textColor=color,
                **{k: (v * scale if k in SCALED_STYLE_KWARGS else v) for k, v in extra.items()},
            )
            for name, (font, size, leading, color, extra) in STYLE_SPECS.items()
        }

    def space(self, points):
        """Scale a vertical gap, keeping it visible at small sizes."""
        return max(1.0, points * self.scale)


# Tags reportlab's paragraph parser understands; everything else is unwrapped
INLINE_TAGS = {'b': 'b', 'strong': 'b', 'i': 'i', 'em': 'i', 'u': 'u', 'br': 'br'}
BLOCK_TAGS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tr'}


def _inline_markup(node):
    """Flatten an HTML node into the small markup subset reportlab supports."""
    if isinstance(node, NavigableString):
        return escape(str(node))

    name = getattr(node, 'name', None)
    if name == 'br':
        return '<br/>'

    inner = ''.join(_inline_markup(child) for child in node.children)
    tag = INLINE_TAGS.get(name)
    if tag:
        return f'<{tag}>{inner}</{tag}>'
    if name == 'a' and node.get('href'):
        return f'<a href="{escape(node["href"], quote=True)}" color="#434E5E">{inner}</a>'
    return inner


def _clean(markup):
    return ' '.join(markup.split())


def html_to_flowables(html, body_style, bullet_style):
    """Turn a stored HTML field into paragraphs and bullets."""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    flowables = []
    loose = []

    def flush_loose():
        text = _clean(''.join(loose))
        loose.clear()
        if text:
            flowables.append(Paragraph(text, body_style))

    for node in soup.children:
        name = getattr(node, 'name', None)
        if name in ('ul', 'ol'):
            flush_loose()
            for index, item in enumerate(node.find_all('li', recursive=False), start=1):
                text = _clean(_inline_markup(item))
                if text:
                    marker = f'{index}.' if name == 'ol' else '•'
                    flowables.append(Paragraph(text, bullet_style, bulletText=marker))
        elif name in BLOCK_TAGS:
            flush_loose()
            text = _clean(_inline_markup(node))
            if text:
                flowables.append(Paragraph(text, body_style))
        else:
            loose.append(_inline_markup(node))

    flush_loose()
    return flowables


def _prose(html, layout):
    return html_to_flowables(html, layout.styles['body'], layout.styles['bullet'])


def _section(title, blocks, layout):
    """A section heading plus its blocks.

    Every block is a ``(sticky, flowing)`` pair: the sticky flowables are held on
    one page, the flowing ones may break across pages. The heading joins the
    first block so it never dangles at the bottom of a page.
    """
    blocks = [(list(sticky), list(flowing)) for sticky, flowing in blocks if sticky or flowing]
    if not blocks:
        return []

    heading = [
        Paragraph(escape(title.upper()), layout.styles['section']),
        HRFlowable(width='100%', thickness=0.75, color=RULE,
                   spaceBefore=layout.space(1), spaceAfter=layout.space(6)),
    ]
    blocks[0] = (heading + blocks[0][0], blocks[0][1])

    story = []
    for sticky, flowing in blocks:
        if sticky:
            story.append(KeepTogether(sticky))
        story.extend(flowing)
    story.append(Spacer(1, layout.space(10)))
    return story


def _summary_blocks(summary, layout):
    flowables = _prose(summary.summary_html, layout) if summary else []
    return [(flowables[:1], flowables[1:])] if flowables else []


def _date_range(job):
    start = job.start_date.strftime('%b %Y') if job.start_date else ''
    if job.is_current or not job.end_date:
        end = 'Present'
    else:
        end = job.end_date.strftime('%b %Y')
    span = ' – '.join(part for part in (start, end) if part)
    return ' · '.join(part for part in (span, job.location) if part)


def _experience(resume, layout):
    jobs = sorted(resume.employment_history.all(), key=lambda job: job.sort_order)
    blocks = []
    for job in jobs:
        header = Table(
            [[
                Paragraph(escape(job.job_title or ''), layout.styles['job']),
                Paragraph(escape(job.company_name or ''), layout.styles['company']),
            ]],
            colWidths=[layout.content_width * 0.6, layout.content_width * 0.4],
        )
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))

        body = _prose(job.description_html, layout)
        sticky = [header, Paragraph(escape(_date_range(job)), layout.styles['meta'])] + body[:1]
        blocks.append((sticky, body[1:] + [Spacer(1, layout.space(8))]))
    return blocks


def _skills(resume, layout):
    keywords = list(resume.keywords.all())
    if not keywords:
        return []

    grouped = {}
    for keyword in keywords:
        grouped.setdefault((keyword.category or '').strip().lower(), []).append(keyword.name)

    ordered = [(key, label) for key, label in SKILL_CATEGORIES if key in grouped]
    known = {key for key, _ in SKILL_CATEGORIES}
    for key in sorted(grouped):
        if key not in known:
            ordered.append((key, key.replace('_', ' ').title() if key else 'Other'))

    rows = [
        [
            Paragraph(escape(label), layout.styles['skill_cat']),
            Paragraph(escape(', '.join(grouped[key])), layout.styles['skill_list']),
        ]
        for key, label in ordered
    ]

    label_width = 1.45 * inch * layout.scale
    table = Table(rows, colWidths=[label_width, layout.content_width - label_width])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), layout.space(4)),
    ]))
    return [([table], [])]


def _education(resume, layout):
    blocks = []
    for edu in resume.education.all():
        meta = ' · '.join(part for part in (edu.school, edu.time) if part)
        blocks.append(([
            Paragraph(escape(edu.degree or ''), layout.styles['entry']),
            Paragraph(escape(meta), layout.styles['entry_meta']),
        ], []))
    return blocks


def _awards(resume, layout):
    blocks = []
    for award in resume.awards.all():
        sticky = [Paragraph(escape(award.name or ''), layout.styles['entry'])]
        if award.description:
            sticky.append(Paragraph(escape(award.description), layout.styles['entry_meta']))
        else:
            sticky.append(Spacer(1, layout.space(4)))
        blocks.append((sticky, []))
    return blocks


def _candidate_location(resume):
    """Where the candidate is, taken from the current role (screeners filter on it)."""
    jobs = sorted(resume.employment_history.all(), key=lambda job: job.sort_order)
    for job in jobs:
        if job.is_current and job.location:
            return job.location
    return next((job.location for job in jobs if job.location), '')


def _draw_banner(canvas, doc, resume, layout):
    canvas.saveState()
    canvas.setFillColor(HEADER_BG)
    canvas.rect(0, PAGE_HEIGHT - layout.banner_height, PAGE_WIDTH, layout.banner_height,
                stroke=0, fill=1)

    top = PAGE_HEIGHT - layout.space(0.45 * inch)
    for text, style in (
        (escape(resume.name or ''), layout.styles['name']),
        (escape(resume.desired_title or resume.current_title or ''), layout.styles['title']),
    ):
        if not text:
            continue
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(layout.content_width, layout.banner_height)
        top -= height
        paragraph.drawOn(canvas, layout.margin, top)
        top -= style.spaceAfter

    separator = ' &nbsp;&nbsp;|&nbsp;&nbsp; '
    contact = separator.join(
        escape(part) for part in (resume.email, resume.phone, _candidate_location(resume)) if part
    )
    links = separator.join(
        f'<a href="{url}">{escape(label)}</a>' for label, url in PROFILE_LINKS
    )
    for line in (contact, links):
        if not line:
            continue
        paragraph = Paragraph(line, layout.styles['contact'])
        _, height = paragraph.wrap(layout.content_width, layout.banner_height)
        top -= height
        paragraph.drawOn(canvas, layout.margin, top)

    canvas.restoreState()


def _draw_footer(canvas, doc, resume, layout):
    canvas.saveState()
    footer = Paragraph(
        f'{escape(resume.name or "")} &nbsp;|&nbsp; chrisriewaldt.com &nbsp;|&nbsp; Page {doc.page}',
        layout.styles['footer'],
    )
    footer.wrap(layout.content_width, 0.4 * inch)
    footer.drawOn(canvas, layout.margin, layout.margin * 0.6)
    canvas.restoreState()


def _story(resume, layout):
    story = [NextPageTemplate('later')]
    story += _section('Career Summary', _summary_blocks(resume.professional_summary, layout), layout)
    story += _section('Work Experience', _experience(resume, layout), layout)
    story += _section('Skills & Tools', _skills(resume, layout), layout)
    story += _section('Education', _education(resume, layout), layout)
    story += _section('Licenses & Awards', _awards(resume, layout), layout)
    return story


def _render(resume, layout):
    """Build the document once. Returns ``(pdf_bytes, page_count)``."""
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=layout.margin,
        rightMargin=layout.margin,
        topMargin=layout.margin,
        bottomMargin=layout.margin,
        title=f'{resume.name} - Resume',
        author=resume.name or '',
        subject=resume.desired_title or resume.current_title or 'Resume',
    )

    first_frame = Frame(
        layout.margin, layout.margin,
        layout.content_width,
        PAGE_HEIGHT - layout.banner_height - layout.margin - layout.space(0.25 * inch),
        id='first', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    later_frame = Frame(
        layout.margin, layout.margin,
        layout.content_width, PAGE_HEIGHT - 2 * layout.margin,
        id='later', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([
        PageTemplate(
            id='first', frames=[first_frame],
            onPage=lambda canvas, doc: _draw_banner(canvas, doc, resume, layout),
            onPageEnd=lambda canvas, doc: _draw_footer(canvas, doc, resume, layout),
        ),
        PageTemplate(
            id='later', frames=[later_frame],
            onPageEnd=lambda canvas, doc: _draw_footer(canvas, doc, resume, layout),
        ),
    ])

    doc.build(_story(resume, layout))
    return buffer.getvalue(), doc.page


def render_resume_pdf(resume, max_pages=DEFAULT_MAX_PAGES):
    """Render a Resume to PDF bytes, shrinking the type to fit ``max_pages``.

    If no step fits the budget, shrinking the type bought nothing, so the
    largest size that reached the fewest pages is returned rather than the
    smallest — an unreadable document that still overflows helps no one.
    """
    attempts = []
    for scale in SCALE_STEPS:
        pdf_bytes, pages = _render(resume, Layout(scale))
        if pages <= max_pages:
            return pdf_bytes
        attempts.append((pages, pdf_bytes))

    fewest = min(pages for pages, _ in attempts)
    # SCALE_STEPS runs largest-first, so this is the biggest type at that count
    return next(pdf_bytes for pages, pdf_bytes in attempts if pages == fewest)
