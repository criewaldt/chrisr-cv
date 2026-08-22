"""Render tailored resume JSON through the existing PDF pipeline.

``resume.pdf.render_resume_pdf`` never touches the ORM -- it only reads attributes
and calls ``.all()`` on related fields. That means a plain object with the same
shape renders identically to a real ``Resume`` row, so tailored resumes reuse the
renderer with zero changes to that module.

PDFs are therefore generated on demand from stored JSON: no file storage, and an
edit to ``resume_json`` shows up in the next download.
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from resume.models import Resume


def _parse_date(value):
    """Accept an ISO string, a date, or None -- pdf.py only calls .strftime()."""
    if value in (None, '', 'null'):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%Y-%m', '%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class _Rel:
    """Stands in for a Django related manager -- pdf.py only ever calls .all()."""

    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)


@dataclass
class SummaryView:
    summary_html: str = ''
    highlights: str = ''

    @property
    def summary(self):
        return self.summary_html


@dataclass
class JobView:
    job_title: str = ''
    company_name: str = ''
    location: str = ''
    start_date: date | None = None
    end_date: date | None = None
    description_html: str = ''
    is_current: bool = False
    sort_order: int = 0


@dataclass
class EducationView:
    degree: str = ''
    school: str = ''
    time: str = ''


@dataclass
class AwardView:
    name: str = ''
    description: str = ''


@dataclass
class KeywordView:
    name: str = ''
    category: str = ''


@dataclass
class TailoredResumeView:
    """Duck-typed stand-in for ``resume.models.Resume``."""

    name: str = ''
    email: str = ''
    phone: str = ''
    current_title: str = ''
    desired_title: str = ''
    professional_summary: SummaryView = field(default_factory=SummaryView)
    employment_history: _Rel = field(default_factory=lambda: _Rel([]))
    education: _Rel = field(default_factory=lambda: _Rel([]))
    awards: _Rel = field(default_factory=lambda: _Rel([]))
    keywords: _Rel = field(default_factory=lambda: _Rel([]))

    @classmethod
    def from_json(cls, data):
        """Build from the JSON shape the tailoring prompt returns.

        Tolerant by design: a missing section renders as an empty section rather
        than raising, because a model that omits ``awards`` should still produce a
        usable resume.
        """
        data = data or {}
        summary = data.get('professional_summary') or {}
        if isinstance(summary, str):
            summary = {'summary_html': summary}

        jobs = [
            JobView(
                job_title=j.get('job_title', ''),
                company_name=j.get('company_name', ''),
                location=j.get('location', ''),
                start_date=_parse_date(j.get('start_date')),
                end_date=_parse_date(j.get('end_date')),
                description_html=j.get('description_html', ''),
                is_current=bool(j.get('is_current')),
                sort_order=int(j.get('sort_order') or index),
            )
            for index, j in enumerate(data.get('employment_history') or [])
        ]

        return cls(
            name=data.get('name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            current_title=data.get('current_title', ''),
            desired_title=data.get('desired_title', ''),
            professional_summary=SummaryView(
                summary_html=summary.get('summary_html') or summary.get('summary') or '',
                highlights=summary.get('highlights', ''),
            ),
            employment_history=_Rel(jobs),
            education=_Rel([
                EducationView(degree=e.get('degree', ''), school=e.get('school', ''),
                              time=e.get('time', ''))
                for e in data.get('education') or []
            ]),
            awards=_Rel([
                AwardView(name=a.get('name', ''), description=a.get('description', ''))
                for a in data.get('awards') or []
            ]),
            keywords=_Rel([
                KeywordView(name=k.get('name', ''), category=k.get('category', ''))
                for k in data.get('keywords') or []
            ]),
        )


def master_resume_json(resume=None):
    """Serialize the stored master resume into the same JSON shape.

    This is the source of truth handed to the tailoring prompt, and the baseline a
    stretch-claim check compares generated text against.
    """
    if resume is None:
        resume = (Resume.objects
                  .select_related('professional_summary')
                  .prefetch_related('employment_history', 'education', 'awards', 'keywords')
                  .first())
    if resume is None:
        return {}

    summary = resume.professional_summary
    return {
        'name': resume.name,
        'email': resume.email,
        'phone': resume.phone,
        'current_title': resume.current_title or '',
        'desired_title': resume.desired_title or '',
        'professional_summary': {
            'summary_html': summary.summary_html if summary else '',
            'highlights': summary.highlights if summary else '',
        },
        'employment_history': [
            {
                'job_title': j.job_title,
                'company_name': j.company_name,
                'location': j.location,
                'start_date': j.start_date.isoformat() if j.start_date else None,
                'end_date': j.end_date.isoformat() if j.end_date else None,
                'description_html': j.description_html,
                'is_current': j.is_current,
                'sort_order': j.sort_order,
            }
            for j in sorted(resume.employment_history.all(), key=lambda j: j.sort_order)
        ],
        'education': [
            {'degree': e.degree, 'school': e.school, 'time': e.time}
            for e in resume.education.all()
        ],
        'awards': [
            {'name': a.name, 'description': a.description}
            for a in resume.awards.all()
        ],
        'keywords': [
            {'name': k.name, 'category': k.category}
            for k in resume.keywords.all()
        ],
    }
