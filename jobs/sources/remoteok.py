"""RemoteOK — free remote job feed. No key. First row of the payload is metadata."""
from .base import JobSourceAdapter, RawPosting, parse_iso, register

API = 'https://remoteok.com/api'


@register
class RemoteOKAdapter(JobSourceAdapter):
    kind = 'remoteok'

    async def fetch(self, session, profile, config):
        response = await session.get(API)
        response.raise_for_status()
        payload = response.json()

        postings = []
        for job in payload:
            # RemoteOK puts a legal/disclaimer object in slot 0; real rows have an id.
            if not isinstance(job, dict) or not job.get('id') or not job.get('position'):
                continue
            # RemoteOK salary fields are already numeric when present.
            salary_min = job.get('salary_min') or None
            salary_max = job.get('salary_max') or None
            if salary_min and int(salary_min) < 10000:
                salary_min = salary_max = None
            postings.append(RawPosting(
                external_id=job.get('id'),
                url=job.get('url') or job.get('apply_url', ''),
                title=job.get('position', ''),
                company=job.get('company', ''),
                location=job.get('location') or 'Remote',
                is_remote=True,
                description_html=job.get('description', ''),
                salary_min=int(salary_min) if salary_min else None,
                salary_max=int(salary_max) if salary_max else None,
                posted_at=parse_iso(job.get('date') or job.get('epoch')),
                raw={'tags': job.get('tags', [])},
            ))
        return postings
