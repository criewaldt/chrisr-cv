"""Arbeitnow — free aggregate job board. No key, no company list needed."""
from .base import JobSourceAdapter, RawPosting, parse_iso, parse_salary, register

API = 'https://www.arbeitnow.com/api/job-board-api'


@register
class ArbeitnowAdapter(JobSourceAdapter):
    kind = 'arbeitnow'

    async def fetch(self, session, profile, config):
        pages = int(config.get('pages', 2))
        postings = []
        for page in range(1, pages + 1):
            response = await session.get(API, params={'page': page})
            response.raise_for_status()
            batch = response.json().get('data', [])
            if not batch:
                break
            for job in batch:
                description = job.get('description', '')
                salary_min, salary_max = parse_salary(description[:4000], strict=True)
                postings.append(RawPosting(
                    external_id=job.get('slug', ''),
                    url=job.get('url', ''),
                    title=job.get('title', ''),
                    company=job.get('company_name', ''),
                    location=job.get('location', ''),
                    is_remote=bool(job.get('remote')),
                    description_html=description,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    posted_at=parse_iso(job.get('created_at')),
                    raw={'tags': job.get('tags', []), 'job_types': job.get('job_types', [])},
                ))
        return postings
