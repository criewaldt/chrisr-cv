"""Manual 'fetch new jobs' run, triggered from the dashboard.

Same shape as jobs/prep.py: the work happens in a background thread and the page
polls, because a full sweep takes far longer than Heroku's 30s router timeout
(~25s to sweep 182 boards, plus triage on whatever survives the pre-filter).

State is tracked on RunLog with no extra field: ``finished_at`` is null while the
run is in flight. A run still unfinished after STALE_AFTER is assumed dead -- the
dyno restarted mid-sweep -- so a new one is allowed to start.
"""
import asyncio
import logging
import threading
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from .discovery import discover
from .models import JobPosting, RunLog, SearchProfile
from .triage_runner import select_for_triage, triage

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)
# Scores are written once per batch, so a run killed mid-sweep loses at most this
# many postings' worth of paid work rather than the whole run.
SCORE_BATCH_SIZE = 60


def current_run():
    """The in-flight run, or None. Ignores runs old enough to be presumed dead."""
    run = RunLog.objects.filter(finished_at__isnull=True).order_by('-started_at').first()
    if run is None:
        return None
    if timezone.now() - run.started_at > STALE_AFTER:
        return None
    return run


def estimated_triage_cost(count=None):
    """Dollar estimate for scoring ``count`` postings, from measured history.

    Shown on the button so a click that spends real money says so beforehand.
    """
    from decimal import Decimal
    from django.db.models import Avg
    from .models import JobScore
    if count is None:
        count = pending_triage_count()
    average = JobScore.objects.aggregate(a=Avg('cost_usd'))['a'] or Decimal('0.005')
    return count * float(average)


def start_score_all():
    """Score every pending posting, ignoring the per-run cap.

    The cap exists so an automated sweep cannot spend without bound. Pressing this
    is an explicit decision to clear the backlog, so the cap does not apply -- but
    the button shows the cost first.
    """
    running = current_run()
    if running is not None:
        return running, False

    run = RunLog.objects.create(slot='score-all', started_at=timezone.now())
    thread = threading.Thread(target=_run_score_all, args=(run.pk,),
                              name=f'score-all-{run.pk}', daemon=False)
    thread.start()
    return run, True


def _run_score_all(run_id):
    """Thread body. Owns its DB connection and must close it."""
    try:
        profile = SearchProfile.active()
        # limit far above any realistic backlog -- this button means "all of it".
        postings, _capped = select_for_triage(profile, limit=100000)
        run = RunLog.objects.get(pk=run_id)
        run.found = len(postings)

        # Score in batches and persist each one. A full backlog sweep can run for
        # several minutes, and triage() only writes its rows at the end -- so an
        # unbatched run that died to a dyno restart would lose everything it had
        # already paid for. A batch caps that loss at one chunk.
        run.save(update_fields=['found'])
        for start in range(0, len(postings), SCORE_BATCH_SIZE):
            batch = postings[start:start + SCORE_BATCH_SIZE]
            scored, errors, stats = asyncio.run(triage(batch, profile))
            run.scored += scored
            run.cost_usd += stats['cost']
            if errors:
                run.errors = list(run.errors or []) + [
                    {'source': 'triage', 'error': str(e)[:300]} for _p, e in errors[:3]]
            run.save(update_fields=['scored', 'cost_usd', 'errors'])
            logger.info('score-all %s: %s/%s scored', run_id, run.scored, len(postings))

        run.finished_at = timezone.now()
        run.save()
        logger.info('score-all %s done: %s scored', run_id, run.scored)

    except Exception as exc:
        logger.exception('score-all %s failed', run_id)
        RunLog.objects.filter(pk=run_id).update(
            finished_at=timezone.now(),
            errors=[{'source': 'run', 'error': f'{type(exc).__name__}: {exc}'[:500]}])
    finally:
        connection.close()


def start_fetch(triage_new=True):
    """Kick off a sweep. Returns the RunLog, reusing one already in flight."""
    running = current_run()
    if running is not None:
        return running, False

    run = RunLog.objects.create(slot='manual', started_at=timezone.now())
    thread = threading.Thread(target=_run, args=(run.pk, triage_new),
                              name=f'fetch-{run.pk}', daemon=False)
    thread.start()
    return run, True


def _run(run_id, triage_new):
    """Thread body. Owns its DB connection and must close it."""
    try:
        profile = SearchProfile.active()
        result = asyncio.run(discover(slot='manual', profile=profile))

        run = RunLog.objects.get(pk=run_id)
        run.sources_run = result.sources_run
        run.found = result.found
        run.new = result.new
        run.filtered = result.filtered
        run.errors = result.errors
        run.save(update_fields=['sources_run', 'found', 'new', 'filtered', 'errors'])

        # The RunLog that discover() created for itself is redundant with ours.
        RunLog.objects.filter(pk=result.pk).exclude(pk=run_id).delete()

        if triage_new:
            postings, _capped = select_for_triage(profile)
            if postings:
                scored, errors, stats = asyncio.run(triage(postings, profile))
                run.scored = scored
                run.cost_usd = stats['cost']
                if errors:
                    run.errors = list(run.errors or []) + [
                        {'source': 'triage', 'error': str(e)[:300]} for _p, e in errors[:5]]

        run.finished_at = timezone.now()
        run.save()
        logger.info('fetch %s done: %s found, %s new, %s scored',
                    run_id, run.found, run.new, run.scored)

    except Exception as exc:
        logger.exception('fetch %s failed', run_id)
        RunLog.objects.filter(pk=run_id).update(
            finished_at=timezone.now(),
            errors=[{'source': 'run', 'error': f'{type(exc).__name__}: {exc}'[:500]}])
    finally:
        connection.close()


def last_finished():
    return RunLog.objects.filter(finished_at__isnull=False).order_by('-finished_at').first()


def pending_triage_count():
    return JobPosting.objects.filter(
        status=JobPosting.STATUS_NEW, score__isnull=True).count()
