"""Public services page. No auth -- this one is for strangers."""
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import EnquiryForm

logger = logging.getLogger(__name__)

# Each accepted submission writes a row and sends mail. Gmail restricts accounts
# that exceed roughly 500 messages a day, so an unthrottled form can cost the
# sending account, not just the database.
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 3600      # seconds


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        # Heroku appends the real client IP; the leftmost entry is client-controlled
        # but is the conventional choice and is only used for throttling and triage.
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _rate_limited(request):
    """True when this IP has already submitted RATE_LIMIT_MAX times this hour.

    Backed by the Django cache. With REDIS_URL set this is shared across dynos;
    on the LocMemCache fallback it is per-process, so the effective limit is the
    cap multiplied by the number of gunicorn workers. Still bounds abuse, and
    setting REDIS_URL makes it exact.
    """
    ip = _client_ip(request)
    if not ip:
        return False
    key = f'studio:enquiry:{ip}'
    count = cache.get(key, 0)
    if count >= RATE_LIMIT_MAX:
        return True
    # add() only sets when absent, so the window starts at the first submission
    # rather than sliding forward with every attempt.
    if not cache.add(key, 1, RATE_LIMIT_WINDOW):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, RATE_LIMIT_WINDOW)
    return False


def _context(form=None, sent=False):
    return {
        'form': form or EnquiryForm(),
        'sent': sent,
        'calendar_url': getattr(settings, 'STUDIO_CALENDAR_URL', ''),
        'loaded_at': time.time(),
    }


@require_http_methods(['GET', 'POST'])
def landing(request):
    if request.method == 'GET':
        return render(request, 'studio/landing.html', _context())

    form = EnquiryForm(request.POST)

    # Throttle before validating so a flood costs as little work as possible.
    if _rate_limited(request):
        logger.warning('studio: rate-limited enquiry from %s', _client_ip(request))
        return render(request, 'studio/landing.html', _context(sent=True))

    # Accept and discard: a bot that sees an error message learns to work around it.
    if form.looks_like_spam:
        logger.info('studio: discarded suspected spam enquiry')
        return render(request, 'studio/landing.html', _context(sent=True))

    if not form.is_valid():
        return render(request, 'studio/landing.html', _context(form=form), status=400)

    enquiry = form.save(commit=False)
    enquiry.source = request.POST.get('source', '')[:40]
    enquiry.ip = _client_ip(request) or None
    enquiry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
    # Saved before the email is attempted. A lead is the point of this page; an SMTP
    # failure must never take it with it.
    enquiry.save()

    try:
        _notify(enquiry)
    except Exception:
        logger.exception('studio: enquiry %s saved but notification failed', enquiry.pk)

    return render(request, 'studio/landing.html', _context(sent=True))


def _notify(enquiry):
    to = getattr(settings, 'STUDIO_NOTIFY_TO', '') or settings.EMAIL_HOST_USER
    if not to:
        logger.warning('studio: no STUDIO_NOTIFY_TO or GMAIL_USER; enquiry %s not emailed',
                       enquiry.pk)
        return

    body = '\n'.join([
        f'{enquiry.name}' + (f' — {enquiry.company}' if enquiry.company else ''),
        f'{enquiry.email}',
        '',
        f'Budget:   {enquiry.budget_label}',
        f'Timeline: {enquiry.timeline_label}',
        '',
        enquiry.message,
        '',
        f'(source: {enquiry.source or "direct"})',
    ])
    subject = f'New enquiry — {enquiry.name}' + (f' at {enquiry.company}' if enquiry.company else '')
    message = EmailMultiAlternatives(
        subject, body, settings.EMAIL_HOST_USER or to, [to],
        reply_to=[enquiry.email],   # replying goes straight to the prospect
    )
    message.send()
