"""Remotive — free aggregate board of remote jobs. No key, no company list needed."""
from .base import JobSourceAdapter, RawPosting, parse_iso, parse_salary, register

API = 'https://remotive.com/api/remote-jobs'


@register
class RemotiveAdapter(JobSourceAdapter):
    kind = 'remotive'

    async def fetch(self, session, profile, config):
        params = {'limit': config.get('limit', 100)}
        if config.get('category'):
            params['category'] = config['category']
        if config.get('search'):
            params['search'] = config['search']
        response = await session.get(API, params=params)
        response.raise_for_status()

        postings = []
        for job in response.json().get('jobs', []):
            salary_min, salary_max = parse_salary(job.get('salary'))
            postings.append(RawPosting(
                external_id=job.get('id'),
                url=job.get('url', ''),
                title=job.get('title', ''),
                company=job.get('company_name', ''),
                location=job.get('candidate_required_location', 'Remote'),
                is_remote=True,
                description_html=job.get('description', ''),
                salary_min=salary_min,
                salary_max=salary_max,
                posted_at=parse_iso(job.get('publication_date')),
                raw={'category': job.get('category'), 'job_type': job.get('job_type')},
            ))
        return postings
