"""Public services page. No auth -- this one is for strangers."""
import logging
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .forms import EnquiryForm

logger = logging.getLogger(__name__)


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

    # Accept and discard: a bot that sees an error message learns to work around it.
    if form.looks_like_spam:
        logger.info('studio: discarded suspected spam enquiry')
        return render(request, 'studio/landing.html', _context(sent=True))

    if not form.is_valid():
        return render(request, 'studio/landing.html', _context(form=form), status=400)

    enquiry = form.save(commit=False)
    enquiry.source = request.POST.get('source', '')[:40]
    enquiry.ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR')
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
