"""Lever public postings API. No key required."""
from .base import JobSourceAdapter, RawPosting, parse_iso, parse_salary, register

API = 'https://api.lever.co/v0/postings/{company}'


@register
class LeverAdapter(JobSourceAdapter):
    kind = 'lever'
    required_config = ('company',)

    async def fetch(self, session, profile, config):
        slug = config['company']
        company = config.get('label') or slug.replace('-', ' ').title()
        response = await session.get(API.format(company=slug), params={'mode': 'json'})
        response.raise_for_status()

        postings = []
        for job in response.json():
            categories = job.get('categories') or {}
            description = job.get('descriptionPlain') or job.get('description') or ''
            lists_html = ''.join(
                f"<h4>{section.get('text','')}</h4>{section.get('content','')}"
                for section in (job.get('lists') or [])
            )
            full = f"{job.get('description','')}{lists_html}"
            salary_min, salary_max = parse_salary(
                categories.get('commitment', '') + ' ' + description[:4000], strict=True)
            postings.append(RawPosting(
                external_id=job.get('id'),
                url=job.get('hostedUrl') or job.get('applyUrl', ''),
                title=job.get('text', ''),
                company=company,
                location=categories.get('location', ''),
                description_html=full,
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=parse_iso(job.get('createdAt')),
                raw={'team': categories.get('team'), 'commitment': categories.get('commitment')},
            ))
        return postings
