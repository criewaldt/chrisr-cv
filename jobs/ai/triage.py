"""Tier 1: score a posting against Chris's profile. Cheap, automatic, high volume.

Two things keep this at roughly a dollar a month:

* The pre-filter has already discarded ~90% of postings for free, so only
  plausible candidates reach an LLM at all.
* Only pre-filter survivors reach an LLM at all, and the per-run cap keeps even a
  large backlog bounded.

The stable half of the prompt sits behind a cache breakpoint, but note that it does
not currently cache: Haiku 4.5 requires a 4,096-token prefix and this one is ~2,100.
See ``client.CACHE_MINIMUM_TOKENS`` for why that is left alone rather than padded.
"""
import asyncio
import logging

from pydantic import BaseModel, Field

from .client import (TRIAGE_CONCURRENCY, TRIAGE_MODEL, as_account_error,
                     build_client, cache_minimum, total_input_tokens, usage_cost)

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 9000


class TriageResult(BaseModel):
    """Schema the model is constrained to. Validated by the SDK on the way back."""

    fit_score: int = Field(ge=0, le=100,
                           description='0-100. How well this role fits the candidate.')
    verdict: str = Field(description='One of: strong, possible, weak, skip')
    reasoning: str = Field(description='Two sentences maximum, specific to this posting.')
    matched_keywords: list[str] = Field(
        default_factory=list, description="Skills the posting wants that the candidate has.")
    missing_keywords: list[str] = Field(
        default_factory=list, description="Skills the posting wants that the candidate lacks.")
    red_flags: list[str] = Field(
        default_factory=list,
        description='Concrete concerns: wrong seniority, wrong stack, unclear comp, in-office conflict.')


SYSTEM_INSTRUCTIONS = """\
You score job postings for a specific software engineer. You are a filter that \
protects his time, not a cheerleader.

Return a fit_score from 0-100 using this rubric:
  85-100  Strong match. Core stack overlap, right seniority, location works. He should apply today.
  70-84   Good match. Most requirements met; some gaps he can credibly bridge.
  55-69   Plausible. Adjacent stack or uncertain seniority. Worth a look on a slow day.
  30-54   Weak. Real mismatch in stack, seniority, or domain.
  0-29    Wrong job. Different discipline, wrong level, or a hard blocker.

Scoring rules, in priority order:
1. Core stack overlap dominates. Python/Django/FastAPI/Celery/Postgres/AWS/GCP work \
scores high. A role centred on a stack he has never used (Rust, Go, C++, Java, .NET, \
mobile, frontend-only) scores low regardless of how good the company is.
2. Seniority must fit. He has 7+ years. Junior/new-grad roles are wrong. Director/VP \
and pure management roles are wrong -- he wants to build.
3. Location must work: remote-US, or the NYC metro. A role requiring relocation or \
onsite presence elsewhere is a hard blocker -- say so in red_flags.
4. Do not inflate. A prestigious company with the wrong stack is still a low score. \
Most postings should land below 70; that is the point.
5. Be concrete in reasoning. "Django and Celery on AWS, exactly his stack" is useful. \
"Great opportunity at a strong company" is noise.

matched_keywords and missing_keywords should name real technologies from the posting, \
not soft skills.

CALIBRATION EXAMPLES

These are the scores expected for archetypal postings. Match this spread; if most of \
your scores land above 70, you are being too generous to be useful.

"Senior Backend Engineer - Python/Django, NYC hybrid, $170-210k. Django REST APIs, \
Celery task pipelines, PostgreSQL, AWS. 5+ years."
  -> 92, strong. Exact stack match across Django, Celery, Postgres and AWS; right \
seniority; NYC. Nothing to bridge.

"Software Engineer, Platform - Remote US. Python services, Kubernetes, Terraform, \
GCP. Some Go exposure helpful."
  -> 78, possible. Python and GCP are core for him; Kubernetes and Terraform are \
credible adjacent gaps he has not shipped. Remote-US works.

"Senior Data Engineer - Snowflake, dbt, Airflow, Databricks. Python required."
  -> 42, weak. Python appears but the role is a modern data-warehouse stack he has \
not worked in. The Python overlap is incidental, not the job.

"Senior Frontend Engineer - React, TypeScript, Next.js. Design systems."
  -> 22, skip. Frontend specialist role. His TypeScript is incidental and there is no \
backend component.

"Staff Site Reliability Engineer - Kubernetes, Prometheus, on-call rotation, Go."
  -> 32, skip. Operations and infrastructure rather than building applications, and \
the primary language is Go.

"Backend Engineer, Payments - London or Dublin. Python, Postgres."
  -> 18, skip. Stack fits well but the location is a hard blocker; he needs remote-US \
or NYC. Put the location conflict in red_flags.

"Software Engineer I - New grad, 0-2 years. Python, some SQL."
  -> 12, skip. He has 7+ years; this is several levels below him."""


def _strip_html(html, limit=1400):
    import re
    text = re.sub(r'<li[^>]*>', '\n  - ', html or '')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return '\n'.join(line.rstrip() for line in text.split('\n') if line.strip())[:limit]


def _candidate_block(master_resume, profile):
    """The stable, cacheable half of the prompt. Must be byte-identical per run.

    This deliberately carries the full role descriptions rather than a summary.
    Two reasons, and both matter: the scorer needs to see what he actually built to
    judge stack overlap, and Haiku will not cache a prefix under 2048 tokens. A
    thinner block scored worse *and* silently disabled caching, which is the single
    biggest cost lever in tier 1.
    """
    roles = []
    for job in master_resume.get('employment_history', []):
        end = 'present' if job['is_current'] else (job['end_date'] or '?')[:7]
        roles.append(
            f"{job['job_title']} - {job['company_name']} ({job['location']}), "
            f"{(job['start_date'] or '?')[:7]} to {end}\n"
            f"{_strip_html(job.get('description_html'))}"
        )

    skills = {}
    for keyword in master_resume.get('keywords', []):
        skills.setdefault(keyword.get('category') or 'other', []).append(keyword['name'])
    skill_lines = '\n'.join(f"  {cat}: {', '.join(names)}" for cat, names in skills.items())

    education = '; '.join(f"{e['degree']} ({e['school']})"
                          for e in master_resume.get('education', []))
    summary = _strip_html(master_resume.get('professional_summary', {}).get('summary_html'), 1600)

    return f"""\
CANDIDATE

Name: {master_resume.get('name', '')}
Current title: {master_resume.get('current_title', '')}
Target title: {master_resume.get('desired_title', '')}
Based in: New York, NY

SUMMARY
{summary}

EXPERIENCE
""" + '\n\n'.join(roles) + f"""

SKILLS
{skill_lines}

EDUCATION
{education}

WHAT HE IS LOOKING FOR
Acceptable locations: remote within the US, or the NYC metro area.
Salary floor: ${profile.min_salary:,} (unstated compensation is not a negative).
Must have: {', '.join(profile.must_have) or 'n/a'}
Strong plus: {', '.join(profile.nice_to_have) or 'n/a'}
Not interested in: {', '.join(profile.exclude_keywords) or 'n/a'}
"""


def _posting_block(posting):
    description = (posting.description_text or '')[:MAX_DESCRIPTION_CHARS]
    salary = posting.salary_display or 'not stated'
    return f"""\
JOB POSTING

Title: {posting.title}
Company: {posting.company}
Location: {posting.location or 'not stated'}{' (remote)' if posting.is_remote else ''}
Salary: {salary}

Description:
{description}

Score this posting."""


async def score_one(client, posting, candidate_block, semaphore):
    """Score a single posting. Returns ``(posting, TriageResult, usage)`` or raises."""
    async with semaphore:
        response = await client.messages.parse(
            model=TRIAGE_MODEL,
            max_tokens=1024,
            system=[
                # Cache breakpoint goes after the stable half. The posting itself
                # lives in the user turn, so the cached prefix never changes.
                {'type': 'text', 'text': SYSTEM_INSTRUCTIONS},
                # Breakpoint after the candidate block: everything above is
                # byte-identical across a run, only the posting varies.
                {'type': 'text', 'text': candidate_block,
                 'cache_control': {'type': 'ephemeral'}},
            ],
            messages=[{'role': 'user', 'content': _posting_block(posting)}],
            output_format=TriageResult,
        )
        return posting, response.parsed_output, response.usage


async def score_batch(postings, profile, master_resume, progress=None):
    """Score many postings concurrently.

    Returns ``(results, errors, stats)``. One posting failing never aborts the
    batch -- an unscored posting stays in the queue for the next run.
    """
    if not postings:
        return [], [], {'cost': 0, 'input_tokens': 0, 'output_tokens': 0, 'cached': 0}

    candidate_block = _candidate_block(master_resume, profile)
    semaphore = asyncio.Semaphore(TRIAGE_CONCURRENCY)
    client = build_client()

    try:
        # Probe with a single call first. An account-level failure (no credits, bad
        # key) would otherwise repeat identically for every posting in the batch.
        try:
            first = await score_one(client, postings[0], candidate_block, semaphore)
        except BaseException as exc:
            fatal = as_account_error(exc)
            if fatal is not None:
                raise fatal from exc
            first = exc

        rest = await asyncio.gather(
            *(score_one(client, p, candidate_block, semaphore) for p in postings[1:]),
            return_exceptions=True,
        ) if len(postings) > 1 else []
        outcomes = [first, *rest]
    finally:
        await client.close()

    results, errors = [], []
    stats = {'cost': 0, 'input_tokens': 0, 'output_tokens': 0, 'cached': 0,
             'cache_eligible': False}

    for posting, outcome in zip(postings, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning('triage failed for %s: %s', posting, outcome)
            errors.append((posting, outcome))
            continue
        _, result, usage = outcome
        stats['cost'] += usage_cost(TRIAGE_MODEL, usage)
        stats['input_tokens'] += total_input_tokens(usage)
        stats['output_tokens'] += usage.output_tokens or 0
        stats['cached'] += getattr(usage, 'cache_read_input_tokens', 0) or 0
        results.append((posting, result, usage))
        if progress:
            progress(len(results) + len(errors), len(postings))

    return results, errors, stats
