"""Ashby public job board API. No key required."""
from .base import JobSourceAdapter, RawPosting, parse_iso, parse_salary, register

API = 'https://api.ashbyhq.com/posting-api/job-board/{name}'


@register
class AshbyAdapter(JobSourceAdapter):
    kind = 'ashby'
    required_config = ('name',)

    async def fetch(self, session, profile, config):
        name = config['name']
        company = config.get('label') or name.replace('-', ' ').title()
        response = await session.get(API.format(name=name),
                                     params={'includeCompensation': 'true'})
        response.raise_for_status()

        postings = []
        for job in response.json().get('jobs', []):
            comp = job.get('compensation') or {}
            summary = comp.get('compensationTierSummary') or ''
            salary_min, salary_max = parse_salary(summary)
            if salary_min is None:
                salary_min, salary_max = parse_salary(
                    (job.get('descriptionPlain') or '')[:4000], strict=True)
            postings.append(RawPosting(
                external_id=job.get('id'),
                url=job.get('jobUrl') or job.get('applyUrl', ''),
                title=job.get('title', ''),
                company=company,
                location=job.get('location', ''),
                is_remote=bool(job.get('isRemote')),
                description_html=job.get('descriptionHtml', ''),
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=parse_iso(job.get('publishedAt')),
                raw={'team': job.get('team'), 'employmentType': job.get('employmentType')},
            ))
        return postings
