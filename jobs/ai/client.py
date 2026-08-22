"""Shared Anthropic client, model config, and cost accounting.

Every call in this package records what it cost, so the dashboard reports real
spend instead of an estimate. That matters here: the whole design is built around
keeping the bill small, and an unmeasured bill drifts.
"""
import os
from decimal import Decimal

from django.conf import settings

# Per 1M tokens (Anthropic first-party rates).
MODEL_PRICING = {
    'claude-haiku-4-5': (Decimal('1.00'), Decimal('5.00')),
    'claude-sonnet-5':  (Decimal('3.00'), Decimal('15.00')),
    'claude-opus-5':    (Decimal('5.00'), Decimal('25.00')),
    'claude-opus-4-8':  (Decimal('5.00'), Decimal('25.00')),
}

# Cache reads bill at ~10% of input; writing to cache costs ~25% more than input.
CACHE_READ_MULTIPLIER = Decimal('0.10')
CACHE_WRITE_MULTIPLIER = Decimal('1.25')

# Minimum cacheable prefix, measured empirically against the API on 2026-08-22:
# a 3,373-token prefix did not cache, 4,206 did. Below this, `cache_control` is
# silently ignored -- no error, no write, no read.
#
# The triage prompt sits near 2,100 tokens, so it does NOT cache today. That is a
# deliberate choice: padding the prompt to ~4k purely to cross this line would mean
# writing 2k tokens of filler the scorer does not need, and every cache miss would
# then cost more. The breakpoint stays in the request so caching switches on for
# free if the prompt ever legitimately grows past the threshold.
CACHE_MINIMUM_TOKENS = {'claude-haiku-4-5': 4096}
DEFAULT_CACHE_MINIMUM = 1024


def cache_minimum(model):
    return CACHE_MINIMUM_TOKENS.get(model, DEFAULT_CACHE_MINIMUM)

# Cheap classification for tier 1, quality for tier 2. Both overridable in settings
# so either stage can be re-pointed without touching code.
TRIAGE_MODEL = getattr(settings, 'JOBS_TRIAGE_MODEL', 'claude-haiku-4-5')
TAILOR_MODEL = getattr(settings, 'JOBS_TAILOR_MODEL', 'claude-opus-5')

# Concurrency ceilings. Unbounded fan-out just trades latency for 429s.
TRIAGE_CONCURRENCY = int(getattr(settings, 'JOBS_TRIAGE_CONCURRENCY', 6))

# Measured on a real posting (2026-08-22), same prompt, Opus 5:
#   effort=high    $0.212  6824 out  88s  -- 18 stretch claims, 4 roles, 35 ATS terms
#   effort=medium  $0.143  4081 out  48s  --  9 stretch claims, 3 roles, 26 ATS terms
#   effort=low     failed -- truncated the JSON mid-string
#   sonnet/medium  $0.095  4661 out  47s  --  8 stretch claims, 2 roles, 10 ATS terms
# medium is the pick: a third cheaper than high with the output still thorough.
# Sonnet is cheaper again but rewrote only half the roles and found a third of the
# keywords, which defeats the point of maximum keyword optimization.
TAILOR_EFFORT = getattr(settings, 'JOBS_TAILOR_EFFORT', 'medium')


class MissingAPIKey(RuntimeError):
    """Raised instead of failing deep inside an async gather with a vague error."""


class AccountError(RuntimeError):
    """An account-level problem: no credits, bad key, suspended org.

    Distinct from a per-request failure because it dooms every other call in the
    batch. Retrying 134 times produces 134 identical errors and no work.
    """


# Substrings that mean "stop the whole run", not "retry this one".
_FATAL_SIGNALS = (
    ('credit balance is too low',
     'Anthropic account is out of credits. Add credits at '
     'console.anthropic.com -> Plans & Billing, then re-run.'),
    ('invalid x-api-key',
     'ANTHROPIC_API_KEY is not valid. Check the value in .env.'),
    ('authentication_error',
     'Anthropic rejected the API key. Check the value in .env.'),
    ('permission_error',
     'This API key lacks permission for the requested model.'),
)


def as_account_error(exc):
    """Return an AccountError when ``exc`` is fatal for the whole run, else None."""
    message = str(exc).lower()
    for signal, guidance in _FATAL_SIGNALS:
        if signal in message:
            return AccountError(guidance)
    return None


def api_key():
    key = os.environ.get('ANTHROPIC_API_KEY') or getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not key:
        raise MissingAPIKey(
            'ANTHROPIC_API_KEY is not set. Add it to .env locally, and to the Heroku '
            'config vars for production. Discovery and pre-filtering work without it; '
            'triage and tailoring do not.'
        )
    return key


def build_client():
    """One async client per run. aiohttp backend handles concurrent calls better."""
    from anthropic import AsyncAnthropic
    try:
        from anthropic import DefaultAioHttpClient
        http_client = DefaultAioHttpClient()
    except ImportError:      # aiohttp extra not installed -- default transport is fine
        http_client = None

    kwargs = {'api_key': api_key(), 'max_retries': 5}
    if http_client is not None:
        kwargs['http_client'] = http_client
    return AsyncAnthropic(**kwargs)


def usage_cost(model, usage):
    """Dollar cost of one call, accounting for cached tokens."""
    input_rate, output_rate = MODEL_PRICING.get(model, (Decimal('0'), Decimal('0')))
    million = Decimal('1000000')

    plain = Decimal(getattr(usage, 'input_tokens', 0) or 0)
    cache_read = Decimal(getattr(usage, 'cache_read_input_tokens', 0) or 0)
    cache_write = Decimal(getattr(usage, 'cache_creation_input_tokens', 0) or 0)
    output = Decimal(getattr(usage, 'output_tokens', 0) or 0)

    cost = (plain * input_rate
            + cache_read * input_rate * CACHE_READ_MULTIPLIER
            + cache_write * input_rate * CACHE_WRITE_MULTIPLIER
            + output * output_rate) / million
    return cost.quantize(Decimal('0.000001'))


def total_input_tokens(usage):
    return ((getattr(usage, 'input_tokens', 0) or 0)
            + (getattr(usage, 'cache_read_input_tokens', 0) or 0)
            + (getattr(usage, 'cache_creation_input_tokens', 0) or 0))
