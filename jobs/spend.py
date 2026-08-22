"""API call and cost accounting, surfaced on the dashboard.

Every LLM call writes its own cost when it completes, so these are measured totals
rather than estimates. The whole system is built around staying cheap, and an
unmeasured bill drifts.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from .models import JobScore, TailoredApplication


def _totals(since=None):
    scores = JobScore.objects.all()
    apps = TailoredApplication.objects.exclude(cost_usd=0)
    if since is not None:
        scores = scores.filter(created_at__gte=since)
        apps = apps.filter(started_at__gte=since)

    s = scores.aggregate(n=Count('id'), c=Sum('cost_usd'))
    a = apps.aggregate(n=Count('id'), c=Sum('cost_usd'))
    triage_n, triage_c = s['n'] or 0, s['c'] or Decimal('0')
    tailor_n, tailor_c = a['n'] or 0, a['c'] or Decimal('0')
    return {
        'triage_calls': triage_n, 'triage_cost': triage_c,
        'tailor_calls': tailor_n, 'tailor_cost': tailor_c,
        'calls': triage_n + tailor_n, 'cost': triage_c + tailor_c,
    }


def summary():
    """All-time, today, and last 30 days, plus the per-unit averages."""
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    all_time = _totals()
    data = {
        'all_time': all_time,
        'today': _totals(today),
        'month': _totals(now - timedelta(days=30)),
    }
    data['avg_triage'] = (all_time['triage_cost'] / all_time['triage_calls']
                          if all_time['triage_calls'] else Decimal('0'))
    data['avg_tailor'] = (all_time['tailor_cost'] / all_time['tailor_calls']
                          if all_time['tailor_calls'] else Decimal('0'))
    return data


def posting_cost(posting):
    """What one posting has cost so far: its score plus any tailoring."""
    total = Decimal('0')
    calls = 0
    score = getattr(posting, 'score', None)
    if score is not None:
        total += score.cost_usd
        calls += 1
    for app in posting.applications.all():
        if app.cost_usd:
            total += app.cost_usd
            calls += 1
    return calls, total
