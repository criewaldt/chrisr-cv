"""Discovery: fetch from every enabled source, dedupe, pre-filter, persist.

This is tier 0 of the pipeline and it costs nothing. By the time it finishes,
every new posting is either ``filtered`` (with a reason) or ``new`` and awaiting
triage -- and only the ``new`` ones will ever cost money.
"""
import hashlib
import logging
import re

from django.utils import timezone

from .filters import prefilter
from .models import JobPosting, JobSource, RunLog, SearchProfile
from .sources import fetch_all

logger = logging.getLogger(__name__)

_PUNCT = re.compile(r'[^a-z0-9]+')


def normalize(text):
    return _PUNCT.sub(' ', (text or '').lower()).strip()


def dedupe_key(company, title):
    """Identity of a role, independent of which board listed it.

    Location is deliberately excluded: the same posting shows up as "NYC" on one
    board and "New York, NY" on another, and including it would split them into
    duplicate cards. The cost is that one company posting the same title in two
    cities collapses to a single row -- acceptable, since every URL is preserved
    in ``alt_urls`` and the extra locations are kept alongside them.
    """
    return hashlib.sha256(f'{normalize(company)}|{normalize(title)}'.encode()).hexdigest()


async def discover(slot='manual', sources=None, profile=None, dry_run=False):
    """Run one discovery pass. Returns a ``RunLog`` (unsaved when ``dry_run``)."""
    profile = profile or await SearchProfile.aactive()
    if sources is None:
        sources = [s async for s in JobSource.objects.filter(enabled=True)]

    run = RunLog(slot=slot, started_at=timezone.now(), sources_run=len(sources))
    if not sources:
        logger.warning('discovery: no enabled sources')
        run.finished_at = timezone.now()
        if not dry_run:
            await run.asave()
        return run

    results = await fetch_all(sources, profile)

    # Load the whole existing corpus in ONE query. Every run re-sees most postings
    # (a board returns its full board each time), so doing a lookup per duplicate
    # meant ~14k sequential round trips to CockroachDB -- about 14 minutes. Loading
    # a few MB once instead takes well under a second.
    seen = {}
    async for row in JobPosting.objects.values(
            'id', 'dedupe_key', 'url', 'alt_urls', 'source_id').aiterator():
        seen[row['dedupe_key']] = row

    errors, to_create, batch_keys = [], [], set()
    alt_updates = {}

    for source, postings, error in results:
        if error is not None:
            errors.append({'source': str(source), 'kind': source.kind,
                           'error': f'{type(error).__name__}: {error}'})
            if not dry_run:
                await _record_failure(source, error)
            continue

        run.found += len(postings)
        for raw in postings:
            key = dedupe_key(raw.company, raw.title)

            if key in seen or key in batch_keys:
                if not dry_run and key in seen:
                    _note_alt_url(seen[key], raw, source, alt_updates)
                continue
            batch_keys.add(key)

            reason = prefilter(raw, profile)
            if reason:
                run.filtered += 1
            else:
                run.new += 1

            to_create.append(JobPosting(
                source=source,
                external_id=raw.external_id,
                url=raw.url[:500],
                dedupe_key=key,
                title=raw.title,
                company=raw.company,
                location=raw.location,
                is_remote=raw.is_remote,
                salary_min=raw.salary_min,
                salary_max=raw.salary_max,
                posted_at=raw.posted_at,
                description_html=raw.description_html,
                description_text=raw.description_text,
                raw=raw.raw,
                status=JobPosting.STATUS_FILTERED if reason else JobPosting.STATUS_NEW,
                filter_reason=(reason or '')[:200],
            ))

        if not dry_run:
            await _record_success(source)

    run.errors = errors
    run.finished_at = timezone.now()

    if dry_run:
        run._preview = to_create
        return run

    if to_create:
        # ignore_conflicts guards the (source, external_id) unique constraint when a
        # board lists the same id twice in one payload.
        await JobPosting.objects.abulk_create(to_create, batch_size=200,
                                              ignore_conflicts=True)

    if alt_updates:
        await JobPosting.objects.abulk_update(
            [JobPosting(id=pk, alt_urls=alts) for pk, alts in alt_updates.items()],
            ['alt_urls'], batch_size=200)

    await run.asave()
    return run


def _note_alt_url(existing, raw, source, alt_updates):
    """Queue an alternate link for a role we already know about.

    Only cross-source duplicates are interesting: the same board returning the same
    job every run is not a second listing, it is the same listing. Filtering on
    source keeps this rare, which is what makes the batched update cheap.
    """
    if not raw.url or existing['source_id'] == source.pk or raw.url == existing['url']:
        return
    alts = alt_updates.get(existing['id'], list(existing['alt_urls'] or []))
    if raw.url in alts or len(alts) >= 10:
        return
    alts.append(raw.url)
    alt_updates[existing['id']] = alts


async def _record_success(source):
    now = timezone.now()
    source.last_run_at = now
    source.last_success_at = now
    source.last_error = ''
    source.consecutive_failures = 0
    await source.asave(update_fields=['last_run_at', 'last_success_at',
                                      'last_error', 'consecutive_failures'])


async def _record_failure(source, error):
    """Fail soft, and stop asking a board that has been broken for five runs."""
    source.last_run_at = timezone.now()
    source.last_error = f'{type(error).__name__}: {error}'[:2000]
    source.consecutive_failures += 1
    fields = ['last_run_at', 'last_error', 'consecutive_failures']
    if source.consecutive_failures >= JobSource.AUTO_DISABLE_AFTER:
        source.enabled = False
        fields.append('enabled')
        logger.error('auto-disabled %s after %s failures', source, source.consecutive_failures)
    await source.asave(update_fields=fields)
