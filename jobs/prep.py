"""Run tier-2 tailoring in a background thread.

Opus tailoring takes 30-90s and Heroku's router times out at 30s, so the button
cannot do the work inline. There is deliberately no Celery worker (that would cost
more per month than the entire AI bill), so a plain thread does it and the page
polls for the result.

Two details make this actually work rather than appear to:

* **The DB connection is closed in the thread's ``finally``.** Django opens a fresh
  connection per thread and never reclaims it; without this, every prep leaks one
  until the dyno restarts.
* **Stale rows are recoverable.** Heroku cycles dynos roughly daily and will
  sometimes kill a prep mid-flight. Anything ``pending`` past
  ``STALE_AFTER_SECONDS`` is surfaced with a Retry button rather than spinning
  forever.
"""
import asyncio
import logging
import threading

from django.db import connection
from django.utils import timezone

from .ai.tailor import apply_patch, tailor
from .models import ApplicantProfile, JobPosting, TailoredApplication
from .resume_view import master_resume_json

logger = logging.getLogger(__name__)


def start_prep(posting, force=False):
    """Create a pending application and kick off tailoring. Returns it immediately.

    Reuses an in-flight row unless ``force``, so a double-click does not pay twice.
    """
    existing = posting.applications.order_by('-version').first()
    if existing and not force:
        if existing.state == TailoredApplication.PENDING and not existing.is_stale:
            return existing
        if existing.state == TailoredApplication.READY:
            return existing

    version = (existing.version + 1) if existing else 1
    application = TailoredApplication.objects.create(
        posting=posting, version=version,
        state=TailoredApplication.PENDING, started_at=timezone.now())

    thread = threading.Thread(target=_run, args=(application.pk,),
                              name=f'prep-{posting.pk}', daemon=False)
    thread.start()
    return application


def _run(application_id):
    """Thread body. Owns its own DB connection and must close it."""
    try:
        application = (TailoredApplication.objects
                       .select_related('posting').get(pk=application_id))
        master = master_resume_json()
        applicant = ApplicantProfile.active()

        result, usage, cost = asyncio.run(
            tailor(application.posting, master, applicant))

        application.resume_json = apply_patch(master, result)
        application.cover_letter_md = result.cover_letter_md or ''
        application.cover_letter_original = result.cover_letter_md or ''
        application.cover_letter_needed = bool(result.cover_letter_needed)
        application.screener_answers = {a.question: a.answer for a in result.screener_answers}
        application.ats_keywords_used = result.ats_keywords_used
        application.stretch_claims = result.stretch_claims
        application.model_used = _tailor_model()
        application.cost_usd = cost
        application.state = TailoredApplication.READY
        application.finished_at = timezone.now()
        application.save()

        JobPosting.objects.filter(pk=application.posting_id, status__in=(
            JobPosting.STATUS_NEW, JobPosting.STATUS_SCORED, 'shortlisted'
        )).update(status='prepped')
        logger.info('prepped %s for $%s', application.posting, cost)

    except Exception as exc:
        logger.exception('prep failed for application %s', application_id)
        TailoredApplication.objects.filter(pk=application_id).update(
            state=TailoredApplication.FAILED, error=str(exc)[:2000],
            finished_at=timezone.now())
    finally:
        # Django will not reclaim a per-thread connection on its own.
        connection.close()


def _tailor_model():
    from .ai.client import TAILOR_MODEL
    return TAILOR_MODEL
