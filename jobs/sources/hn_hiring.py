"""Hacker News 'Who is hiring?' — free via the Algolia API.

The monthly thread is one of the better sources of small-company roles that never
reach an aggregator. Each top-level comment is one job, in freeform text, so the
parsing is necessarily loose: the first line carries company and location by
convention, and triage reads the rest.
"""
import re

from .base import JobSourceAdapter, RawPosting, parse_iso, register

SEARCH = 'https://hn.algolia.com/api/v1/search_by_date'
ITEM = 'https://hn.algolia.com/api/v1/items/{id}'

# Convention is "Company | Role | Location | REMOTE | tech, stack"
_SEP = re.compile(r'\s*\|\s*|\s+-\s+|\s*—\s*')
_REMOTE = re.compile(r'\bremote\b', re.I)
_TAGS = re.compile(r'<[^>]+>')


@register
class HNHiringAdapter(JobSourceAdapter):
    kind = 'hn_hiring'

    async def fetch(self, session, profile, config):
        # The canonical threads are all posted by the 'whoishiring' account. A text
        # query instead returns whatever Ask HN posts happen to be recent.
        threads = await session.get(SEARCH, params={
            'tags': 'story,author_whoishiring',
            'hitsPerPage': int(config.get('threads', 2)),
        })
        threads.raise_for_status()
        hits = [h for h in threads.json().get('hits', [])
                if 'who is hiring' in (h.get('title') or '').lower()]
        if not hits:
            return []

        postings = []
        for hit in hits:
            detail = await session.get(ITEM.format(id=hit['objectID']))
            detail.raise_for_status()
            for child in detail.json().get('children') or []:
                posting = self._parse(child, hit['objectID'])
                if posting:
                    postings.append(posting)
        return postings

    def _parse(self, comment, thread_id):
        text = comment.get('text') or ''
        if not text or comment.get('author') is None:
            return None
        plain = _TAGS.sub(' ', text).replace('&#x2F;', '/').replace('&amp;', '&')
        first_line = plain.strip().split('\n')[0][:300]
        parts = [p.strip() for p in _SEP.split(first_line) if p.strip()]
        if len(parts) < 2:
            return None

        company, title = parts[0][:200], parts[1][:300]
        location = next((p for p in parts[2:5] if not _REMOTE.match(p)), '')
        return RawPosting(
            external_id=f"hn-{comment.get('id')}",
            url=f"https://news.ycombinator.com/item?id={comment.get('id')}",
            title=title,
            company=company,
            location=location or ('Remote' if _REMOTE.search(first_line) else ''),
            is_remote=bool(_REMOTE.search(first_line)),
            description_html=text,
            posted_at=parse_iso(comment.get('created_at')),
            raw={'thread': thread_id},
        )
