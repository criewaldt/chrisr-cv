"""Tier 2: generate a tailored resume, cover letter, and screener answers.

This only ever runs when Chris clicks Prep on a specific job. That single decision
is what keeps the system cheap -- the expensive model never touches the ~50 jobs a
day he scrolls past.

Two design choices worth knowing:

*Patch, not full rewrite.* The model returns only what changes -- a rewritten
summary, rewritten bullets keyed by company, a reordered keyword selection -- and
those are merged onto the master resume. Output tokens dominate the cost at
$25/1M, so returning ~1,500 tokens instead of ~4,000 roughly halves the bill. It
is also more reliable: dates, employers, and job titles come from the database and
cannot be hallucinated or dropped.

*Maximum keyword optimization, no stretch readout.* The prompt is allowed to
present real experience in the posting's language and to claim credible adjacent
familiarity. It used to also return an exhaustive list of everything it reached on;
that was dropped at Chris's request -- he reads his own resume and knows his own
background, and the list was a sizeable share of the output tokens at $25/1M.

The factual guardrails are independent of that and remain: employers, titles,
locations, and dates come from the database and are never model-writable, and
inventing a degree, certification, or metric is still forbidden.
"""
import json
import logging

from pydantic import BaseModel, Field

from .client import (TAILOR_EFFORT, TAILOR_MODEL, as_account_error, build_client,
                     usage_cost)

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 14000


class RoleBullets(BaseModel):
    company_name: str = Field(description='Must exactly match a company from the master resume.')
    description_html: str = Field(
        description='Rewritten bullets as <ul><li>...</li></ul>. Same facts, retargeted language.')


class ScreenerAnswer(BaseModel):
    question: str
    answer: str


class TailorResult(BaseModel):
    """The patch applied over the master resume, plus the extras the kit needs."""

    desired_title: str = Field(description="Headline title, mirroring the posting's own wording.")
    summary_html: str = Field(description='Rewritten professional summary as HTML.')
    roles: list[RoleBullets] = Field(description='Rewritten bullets, one entry per role changed.')
    keyword_order: list[str] = Field(
        description='Master-resume skill names to keep, most relevant first.')
    ats_keywords_used: list[str] = Field(
        description='Keywords from the posting deliberately worked into the resume.')
    cover_letter_needed: bool = Field(description='Whether this posting asks for or expects one.')
    cover_letter_md: str = Field(description='Cover letter in plain markdown. Empty if not needed.')
    screener_answers: list[ScreenerAnswer] = Field(
        description='Likely application-form questions with ready answers.')


SYSTEM_INSTRUCTIONS = """\
You tailor a software engineer's resume to a specific job posting, in MAXIMUM \
KEYWORD OPTIMIZATION mode. The goal is to pass automated ATS screening and then \
read well to a human.

WHAT TO DO
1. Extract every ATS-relevant term from the posting: languages, frameworks, tools, \
cloud services, methodologies, domain vocabulary, and seniority signals.
2. Rewrite the professional summary and the role bullets to carry those terms at \
high density, while still reading as natural English a hiring manager would respect.
3. Mirror the posting's own vocabulary. If it says "distributed systems", use that \
phrase rather than "large-scale backends".
4. Reorder and trim the skill list so the terms this posting cares about come first.
5. Write a cover letter only if the posting asks for or expects one. See the COVER \
LETTER section below -- it is a hard specification, not a suggestion.
6. Draft answers to the screener questions this employer is likely to ask.

HARD RULES
- Never change employer names, job titles, locations, or dates. Those come from the \
database and are returned to you for context only.
- Never invent an employer, a degree, a certification, or a metric. Numbers must \
come from the master resume.
- You MAY present his real experience in the posting's language, and you MAY claim \
familiarity with adjacent tools where his actual experience makes that credible.
- Return bullets as <ul><li>...</li></ul>. Keep each bullet to one or two lines.
- Only return roles you actually rewrote, and match company_name exactly.

COVER LETTER: ONE PARAGRAPH, 90-130 WORDS

It has two readers and must satisfy both.

The human skims for roughly seven seconds and is pattern-matching for reasons to \
say no. So:
- The first clause does most of the work. Lead with the exact role title, the \
company name, and the single strongest credential. Never open with "I am excited \
to apply", "I am writing to express interest", or any variant -- those cost the \
opening clause and signal a template.
- Anchor credibility on ONE specific, quantified achievement from the master resume \
that maps to this posting's central problem. A number beats any adjective.
- Show you read the posting. One concrete detail about this company, product, or \
problem -- something that could not appear in a letter to anyone else.
- Close with quiet confidence in one short clause. Do not plead, do not thank them \
for their time, do not say you would love the opportunity.
- Cut every sentence that would survive a find-and-replace of the company name.

The parser scores keyword overlap and has no sense of prose. So:
- Use the posting's exact job title verbatim, and the company name, once each.
- Work in 4-6 hard skills as literal strings matching the posting's spelling \
("PostgreSQL" not "Postgres" if that is how they wrote it).
- Plain prose only: no markdown headers, bullets, bold, or links. No salutation \
line and no sign-off -- the document template supplies those.

Write it as one flowing paragraph. Concrete nouns and verbs, no hedging, no \
adverbs of enthusiasm. If it reads like it could have been sent to five companies, \
it has failed."""


def _posting_block(posting):
    return f"""\
JOB POSTING

Title: {posting.title}
Company: {posting.company}
Location: {posting.location or 'not stated'}{' (remote)' if posting.is_remote else ''}
Salary: {posting.salary_display or 'not stated'}

{(posting.description_text or '')[:MAX_DESCRIPTION_CHARS]}"""


def _applicant_block(applicant):
    if applicant is None:
        return 'No standing answers on file.'
    rows = [
        f'Authorized to work in the US: {"yes" if applicant.work_authorized else "no"}',
        f'Requires visa sponsorship: {"yes" if applicant.needs_sponsorship else "no"}',
        f'Salary expectation: {applicant.salary_expectation or "open / negotiable"}',
        f'Notice period: {applicant.notice_period or "2 weeks"}',
        f'Willing to relocate: {"yes" if applicant.willing_to_relocate else "no"}',
        f'Preferred locations: {", ".join(applicant.preferred_locations or []) or "n/a"}',
        f'LinkedIn: {applicant.linkedin_url}',
        f'GitHub: {applicant.github_url}',
        f'Portfolio: {applicant.portfolio_url}',
    ]
    for question, answer in (applicant.extra_answers or {}).items():
        rows.append(f'{question}: {answer}')
    return '\n'.join(rows)


async def tailor(posting, master_resume, applicant=None):
    """Generate the patch for one posting. Returns ``(TailorResult, usage, cost)``."""
    client = build_client()
    try:
        response = await client.messages.parse(
            model=TAILOR_MODEL,
            # Headroom matters: at lower effort the model has truncated a long
            # response mid-JSON, which fails validation and wastes the whole call.
            max_tokens=12000,
            thinking={'type': 'adaptive'},
            output_config={'effort': TAILOR_EFFORT},
            system=[
                {'type': 'text', 'text': SYSTEM_INSTRUCTIONS},
                # The resume and standing answers are identical for every job, so
                # they sit behind a cache breakpoint with a 1h TTL -- prepping
                # several jobs in one sitting then pays for this prefix once.
                # Unlike Haiku's 4k floor, Opus caches from ~1k tokens.
                {'type': 'text',
                 'text': 'MASTER RESUME (the only source of truth for facts)\n'
                         + json.dumps(master_resume, separators=(',', ':'))},
                {'type': 'text', 'text': 'STANDING ANSWERS\n' + _applicant_block(applicant),
                 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}},
            ],
            messages=[{'role': 'user', 'content': _posting_block(posting)}],
            output_format=TailorResult,
        )
    except BaseException as exc:
        fatal = as_account_error(exc)
        raise fatal from exc if fatal is not None else exc
    finally:
        await client.close()

    return response.parsed_output, response.usage, usage_cost(TAILOR_MODEL, response.usage)


def apply_patch(master_resume, result):
    """Merge the model's patch onto the master resume.

    Employers, titles, locations, and dates are copied straight from the master --
    the model never gets to touch them, so they cannot drift.
    """
    tailored = json.loads(json.dumps(master_resume))
    tailored['desired_title'] = result.desired_title or tailored.get('desired_title', '')
    tailored.setdefault('professional_summary', {})['summary_html'] = result.summary_html

    rewritten = {r.company_name.strip().lower(): r.description_html for r in result.roles}
    for job in tailored.get('employment_history', []):
        replacement = rewritten.get((job.get('company_name') or '').strip().lower())
        if replacement:
            job['description_html'] = replacement

    # Reorder keywords to the model's ranking; anything it dropped falls to the end
    # rather than disappearing, so the skills section never silently loses a category.
    by_name = {k['name'].strip().lower(): k for k in tailored.get('keywords', [])}
    ordered, seen = [], set()
    for name in result.keyword_order:
        keyword = by_name.get((name or '').strip().lower())
        if keyword and id(keyword) not in seen:
            ordered.append(keyword)
            seen.add(id(keyword))
    ordered += [k for k in tailored.get('keywords', []) if id(k) not in seen]
    tailored['keywords'] = ordered
    return tailored
