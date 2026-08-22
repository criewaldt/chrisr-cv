"""Job source adapter contract and the async fan-out that drives them.

Adapters are deliberately dumb: fetch, normalize, return. Everything about
deduping, filtering, and persistence happens upstream in ``jobs.discovery`` so an
adapter is ~40 lines and adding a board is one file.

Fan-out is async because these are ~20 independent HTTP calls; ``gather`` with
``return_exceptions=True`` means one dead board is recorded against its own
JobSource and never sinks the run.
"""
import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = 'ChrisRiewaldt-JobHunt/1.0 (+https://chrisriewaldt.com)'
REQUEST_TIMEOUT = 20.0
# With ~180 sources, unbounded gather would open ~180 sockets at once and invite
# throttling. 25 in flight keeps a full sweep well under two minutes.
MAX_CONCURRENT_SOURCES = 25

# Salary strings vary wildly ("$150,000 - $180,000", "150k-180k", "$75/hr").
_MONEY = re.compile(r'\$?\s*(\d{1,3}(?:,\d{3})+|\d{2,7}(?:\.\d+)?)\s*([kK])?')
_REMOTE_HINT = re.compile(r'\bremote\b|\bwork from home\b|\banywhere\b|\bdistributed\b', re.I)


@dataclass
class RawPosting:
    """One posting, normalized. The only thing an adapter returns."""

    external_id: str
    url: str
    title: str
    company: str
    location: str = ''
    is_remote: bool = False
    description_html: str = ''
    salary_min: int | None = None
    salary_max: int | None = None
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)

    def __post_init__(self):
        self.external_id = str(self.external_id)[:200]
        self.title = (self.title or '').strip()[:300]
        self.company = (self.company or '').strip()[:200]
        self.location = (self.location or '').strip()[:200]
        if not self.is_remote:
            self.is_remote = bool(_REMOTE_HINT.search(self.location))

    @property
    def description_text(self):
        if not self.description_html:
            return ''
        return BeautifulSoup(self.description_html, 'html.parser').get_text(' ', strip=True)


class JobSourceAdapter(ABC):
    """Base for every board adapter."""

    kind: str = ''
    #: Config keys that must be present for this adapter to run at all.
    required_config: tuple = ()

    def validate(self, config):
        missing = [k for k in self.required_config if not (config or {}).get(k)]
        if missing:
            raise ValueError(f'{self.kind}: missing config {", ".join(missing)}')

    @abstractmethod
    async def fetch(self, session: httpx.AsyncClient, profile, config: dict) -> list[RawPosting]:
        """Return normalized postings. Raise on failure -- the runner records it."""


# --- shared helpers -------------------------------------------------------

def parse_salary(text, strict=False):
    """Best-effort (min, max) from a salary string. Returns (None, None) when unsure.

    Deliberately conservative: a wrong number here feeds the pre-filter's salary
    rule and would silently reject good jobs, so ambiguity yields nothing.

    ``strict=True`` is for scraping free-form description text, where any number
    between 10k and 1M can look like a salary. It requires two distinct values --
    a real posted range -- because a lone number in a job description is far more
    often a revenue figure or a headcount than it is compensation.
    """
    if not text:
        return None, None
    values = []
    for amount, k in _MONEY.findall(str(text)):
        try:
            value = float(amount.replace(',', ''))
        except ValueError:
            continue
        if k:
            value *= 1000
        # Ignore hourly rates and stray small numbers; annual salaries only.
        if 10000 <= value <= 1000000:
            values.append(int(value))
    distinct = sorted(set(values))
    if not distinct:
        return None, None
    if len(distinct) == 1:
        # A single number is only trustworthy from a dedicated salary field.
        return (None, None) if strict else (distinct[0], distinct[0])
    return distinct[0], distinct[-1]


def parse_iso(value):
    """Parse the assorted timestamp shapes job boards emit."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt_timezone.utc)
    if isinstance(value, (int, float)):
        # Boards emit both seconds and milliseconds since epoch.
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, tz=dt_timezone.utc)
        except (ValueError, OSError):
            return None
    text = str(value).strip().replace('Z', '+00:00')
    for parse in (datetime.fromisoformat,
                  lambda t: datetime.strptime(t, '%Y-%m-%d'),
                  lambda t: datetime.strptime(t, '%a, %d %b %Y %H:%M:%S %z')):
        try:
            parsed = parse(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


# --- registry + runner ----------------------------------------------------

_REGISTRY: dict[str, JobSourceAdapter] = {}


def register(adapter_cls):
    _REGISTRY[adapter_cls.kind] = adapter_cls()
    return adapter_cls


def get_adapter(kind):
    if kind not in _REGISTRY:
        raise KeyError(f'No adapter registered for {kind!r}. Known: {sorted(_REGISTRY)}')
    return _REGISTRY[kind]


def registered_kinds():
    return sorted(_REGISTRY)


async def fetch_all(sources, profile):
    """Fan out across sources concurrently.

    Returns ``[(source, postings, error), ...]`` in the order given. Never raises:
    a broken board yields ``error`` and the rest of the run continues.
    """
    if not sources:
        return []

    headers = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, headers=headers,
                                 follow_redirects=True) as session:

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOURCES)

        async def run_one(source):
            async with semaphore:
                adapter = get_adapter(source.kind)
                adapter.validate(source.config)
                return await adapter.fetch(session, profile, source.config or {})

        results = await asyncio.gather(*(run_one(s) for s in sources),
                                       return_exceptions=True)

    out = []
    for source, result in zip(sources, results):
        if isinstance(result, BaseException):
            logger.warning('source %s failed: %s', source, result)
            out.append((source, [], result))
        else:
            out.append((source, result, None))
    return out
