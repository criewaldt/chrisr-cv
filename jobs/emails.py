"""Digest emails: three a day, each covering everything since the previous send.

The window starts at the last *actual* send rather than a fixed clock time, so a
skipped or failed digest rolls its contents into the next one instead of dropping
them on the floor.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import ApplicationEvent, DigestSend, JobPosting, SearchProfile

logger = logging.getLogger(__name__)

SLOT_LABELS = {'cli': 'manual', 'manual': 'manual'}
SITE = getattr(settings, 'JOBS_SITE_URL', 'https://chrisriewaldt.com')


def window_for(slot, now=None):
    """(start, end) covering everything since the last email of any slot."""
    now = now or timezone.now()
    last = DigestSend.objects.filter(skipped=False).order_by('-sent_at').first()
    start = last.sent_at if last else now - timedelta(hours=24)
    return start, now


def gather(slot, now=None):
    profile = SearchProfile.active()
    start, end = window_for(slot, now)

    new_jobs = list(JobPosting.objects
                    .filter(discovered_at__gte=start, discovered_at__lt=end,
                            score__fit_score__gte=profile.min_score_to_show)
                    .exclude(status__in=('dismissed', 'rejected', 'closed'))
                    .select_related('score', 'source')
                    .order_by('-score__fit_score')[:profile.daily_inbox_size])

    applied = list(ApplicationEvent.objects
                   .filter(status='applied', occurred_at__gte=start, occurred_at__lt=end)
                   .select_related('posting').order_by('-occurred_at'))

    return {'slot': slot, 'start': start, 'end': end,
            'new_jobs': new_jobs, 'applied': applied, 'profile': profile}


def render_text(data):
    lines = [f"JOB DIGEST — {SLOT_LABELS.get(data['slot'], data['slot'])}", '']
    if data['new_jobs']:
        lines.append(f"NEW OPPORTUNITIES ({len(data['new_jobs'])})")
        for p in data['new_jobs']:
            salary = f'  {p.salary_display}' if p.salary_display else ''
            lines += [
                f"  [{p.score.fit_score}] {p.title} — {p.company}",
                f"       {p.location or 'location n/a'}{salary}  ({p.source.kind})",
                f"       {p.score.reasoning[:150]}",
                f"       {SITE}/jobs/job/{p.pk}/",
                '']
    else:
        lines += ['NEW OPPORTUNITIES: none above your score floor since the last email.', '']

    if data['applied']:
        lines.append(f"APPLIED SINCE LAST EMAIL ({len(data['applied'])})")
        for e in data['applied']:
            lines.append(f"  {e.occurred_at:%b %d %H:%M}  {e.posting.title} — {e.posting.company}")
        lines.append('')
    else:
        lines += ['APPLIED SINCE LAST EMAIL: none.', '']

    lines += _day_wrap(data)
    lines.append(f"{SITE}/jobs/")
    return '\n'.join(lines)


def _day_wrap(data):
    """Today's totals, appended to every digest."""
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    found = JobPosting.objects.filter(discovered_at__gte=today).count()
    filtered = JobPosting.objects.filter(discovered_at__gte=today, status='filtered').count()
    applied = ApplicationEvent.objects.filter(status='applied', occurred_at__gte=today).count()
    target = data['profile'].daily_application_target
    return ['— DAY WRAP —',
            f'  discovered today: {found}  ({filtered} filtered out for free)',
            f'  applied today: {applied} of a {target}/day target',
            '']


def subject_for(data):
    return (f"Jobs — {len(data['new_jobs'])} new, "
            f"{len(data['applied'])} applied since last digest")


def send_digest(slot, to=None, now=None, dry_run=False):
    """Send one digest. Returns the ``DigestSend`` row (unsaved when dry_run)."""
    data = gather(slot, now)
    now = data['end']
    record = DigestSend(slot=slot, sent_at=now, window_start=data['start'],
                        window_end=now, new_job_count=len(data['new_jobs']),
                        applied_count=len(data['applied']))

    # Suppress only when there is genuinely nothing to say, so a quiet inbox means
    # quiet rather than broken.
    if not data['new_jobs'] and not data['applied']:
        record.skipped = True
        record.skip_reason = 'no new matches and nothing applied to'
        if not dry_run:
            record.save()
        return record, ''

    body = render_text(data)
    if dry_run:
        return record, body

    recipient = to or getattr(settings, 'JOBS_DIGEST_TO', '') or settings.EMAIL_HOST_USER
    sender = settings.EMAIL_HOST_USER or recipient
    if not recipient:
        # Without this the send is handed [None] and fails deep inside smtplib with
        # nothing pointing at the actual cause.
        raise RuntimeError(
            'No digest recipient. Set JOBS_DIGEST_TO, or GMAIL_USER which it falls '
            'back to. Everything else in the cycle already ran and was saved.')
    message = EmailMultiAlternatives(subject_for(data), body, sender, [recipient])
    message.send()
    record.save()
    logger.info('digest %s sent: %s new, %s applied',
                slot, record.new_job_count, record.applied_count)
    return record, body
