"""Select which postings to triage, score them, and persist the results.

The selection step is where Chris's real ceiling is enforced. Discovery is
deliberately wide, but he can only apply to 10-20 jobs a day, so there is no
point paying to score an unbounded backlog. When survivors exceed the per-run
cap, the free keyword ranking decides who goes first -- deprioritized postings
stay queued and compete again next run, so nothing is lost, only delayed.
"""
import logging
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from .ai.triage import score_batch
from .models import JobPosting, JobScore, SearchProfile
from .ranking import rank
from .resume_view import master_resume_json

logger = logging.getLogger(__name__)


def select_for_triage(profile, limit=None, max_age_days=None, queryset=None):
    """Postings worth spending a triage call on, best-first.

    Ordering matters: with a cap in play, the free ranking decides who gets scored
    this run. Without it, selection would effectively be arbitrary.
    """
    queryset = queryset if queryset is not None else JobPosting.objects.filter(
        status=JobPosting.STATUS_NEW, score__isnull=True)

    if max_age_days:
        cutoff = timezone.now() - timedelta(days=max_age_days)
        queryset = queryset.filter(posted_at__gte=cutoff)

    limit = limit or profile.max_triage_per_run
    candidates = list(queryset.select_related('source')[:2000])
    if len(candidates) <= limit:
        return candidates, False

    ranked = rank(candidates, profile, master_resume_json(), limit=limit)
    return [posting for _score, _terms, posting in ranked], True


async def triage(postings, profile=None, master_resume=None, progress=None):
    """Score postings and write ``JobScore`` rows. Returns ``(scored, errors, stats)``."""
    if not postings:
        return 0, [], {'cost': 0, 'cached': 0, 'input_tokens': 0, 'output_tokens': 0}

    profile = profile or await SearchProfile.aactive()
    master_resume = master_resume or await sync_to_async(master_resume_json)()

    results, errors, stats = await score_batch(postings, profile, master_resume, progress)

    scores = [
        JobScore(
            posting=posting,
            fit_score=result.fit_score,
            verdict=result.verdict,
            reasoning=result.reasoning,
            matched_keywords=result.matched_keywords,
            missing_keywords=result.missing_keywords,
            red_flags=result.red_flags,
            model_used=_model_of(usage),
            input_tokens=(usage.input_tokens or 0)
                         + (getattr(usage, 'cache_read_input_tokens', 0) or 0),
            output_tokens=usage.output_tokens or 0,
            cost_usd=_cost_of(usage),
        )
        for posting, result, usage in results
    ]
    if scores:
        await JobScore.objects.abulk_create(scores, batch_size=100, ignore_conflicts=True)
        scored_ids = [s.posting_id for s in scores]
        await JobPosting.objects.filter(id__in=scored_ids).aupdate(
            status=JobPosting.STATUS_SCORED)

    return len(scores), errors, stats


def _model_of(usage):
    from .ai.client import TRIAGE_MODEL
    return TRIAGE_MODEL


def _cost_of(usage):
    from .ai.client import TRIAGE_MODEL, usage_cost
    return usage_cost(TRIAGE_MODEL, usage)
