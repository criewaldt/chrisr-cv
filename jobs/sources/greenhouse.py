"""Greenhouse public job board API. No key required."""
from .base import JobSourceAdapter, RawPosting, parse_iso, parse_salary, register

API = 'https://boards-api.greenhouse.io/v1/boards/{token}/jobs'


@register
class GreenhouseAdapter(JobSourceAdapter):
    kind = 'greenhouse'
    required_config = ('token',)

    async def fetch(self, session, profile, config):
        token = config['token']
        company = config.get('company') or token.replace('-', ' ').title()
        response = await session.get(API.format(token=token), params={'content': 'true'})
        response.raise_for_status()

        postings = []
        for job in response.json().get('jobs', []):
            location = (job.get('location') or {}).get('name', '')
            # Greenhouse returns description HTML entity-encoded inside JSON.
            description = job.get('content', '') or ''
            if '&lt;' in description:
                import html
                description = html.unescape(description)
            salary_min, salary_max = parse_salary(description[:4000], strict=True)
            postings.append(RawPosting(
                external_id=job.get('id'),
                url=job.get('absolute_url', ''),
                title=job.get('title', ''),
                company=company,
                location=location,
                description_html=description,
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=parse_iso(job.get('updated_at') or job.get('first_published')),
                raw={'departments': [d.get('name') for d in job.get('departments', [])]},
            ))
        return postings
