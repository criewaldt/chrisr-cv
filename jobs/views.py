"""Dashboard. Every view is staff-only -- this is Chris's private job search on a
public domain.

The inbox is capacity-aware by design. Discovery is deliberately wide (180+ boards),
but he can only apply to 10-20 jobs a day, so the inbox shows ``daily_inbox_size``
and the rest wait their turn. Overflow competes on score next run rather than
expiring, so a good job found on a busy day is not lost.

It also works before any LLM has run: unscored postings fall back to the free
keyword-overlap ranking, so the dashboard is useful with an empty API balance.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from resume.pdf import PROFILE_LINKS, render_resume_pdf

from .cover_pdf import render_cover_letter_pdf
from .docx_export import render_resume_docx

from .models import (ApplicantProfile, ApplicationEvent, JobPosting, JobSource,
                     SearchProfile, TailoredApplication)
from .prep import start_prep
from .ranking import rank
from .resume_view import TailoredResumeView, master_resume_json

ACTIONABLE = ('scored', 'shortlisted', 'prepped')


def _profile():
    profile = SearchProfile.active()
    if profile is None:
        raise Http404('No active SearchProfile. Create one in the admin first.')
    return profile


@staff_member_required
def inbox(request):
    """Ranked queue of jobs worth applying to, capped at daily capacity."""
    profile = _profile()
    status = request.GET.get('status', 'open')
    show_all = request.GET.get('all') == '1'

    postings = (JobPosting.objects
                .select_related('score', 'source')
                .prefetch_related('applications'))

    if status == 'open':
        postings = postings.filter(status__in=ACTIONABLE)
    elif status != 'any':
        postings = postings.filter(status=status)

    if request.GET.get('q'):
        query = request.GET['q']
        postings = postings.filter(Q(title__icontains=query) | Q(company__icontains=query))

    scored = list(postings.filter(score__isnull=False,
                                  score__fit_score__gte=profile.min_score_to_show)
                  .order_by('-score__fit_score', '-discovered_at'))
    unscored = list(postings.filter(score__isnull=True).order_by('-discovered_at')[:400])

    # Before triage has run there are no scores, so fall back to the free ranking
    # rather than showing an arbitrary date order.
    ranked_unscored = []
    if unscored:
        master = master_resume_json()
        ranked_unscored = [(round(s), p) for s, _terms, p in rank(unscored, profile, master)]

    limit = None if show_all else profile.daily_inbox_size
    rows = ([(p.score.fit_score, p, True) for p in scored]
            + [(s, p, False) for s, p in ranked_unscored])
    visible = rows[:limit] if limit else rows

    return render(request, 'jobs/inbox.html', {
        'rows': visible,
        'total': len(rows),
        'hidden': max(0, len(rows) - len(visible)),
        'show_all': show_all,
        'profile': profile,
        'status': status,
        'q': request.GET.get('q', ''),
        'counts': _counts(),
        'pending_triage': JobPosting.objects.filter(
            status=JobPosting.STATUS_NEW, score__isnull=True).count(),
    })


def _counts():
    rows = (JobPosting.objects.values('status')
            .annotate(n=Count('id')).order_by('-n'))
    return {r['status']: r['n'] for r in rows}


@staff_member_required
def detail(request, pk):
    """One job: the posting, its score, and the application kit once prepped."""
    posting = get_object_or_404(
        JobPosting.objects.select_related('score', 'source'), pk=pk)
    application = posting.current_application
    return render(request, 'jobs/detail.html', {
        'posting': posting,
        'score': getattr(posting, 'score', None),
        'application': application,
        'applicant': ApplicantProfile.active(),
        'events': posting.events.all()[:20],
        'statuses': JobPosting.STATUS_CHOICES,
    })


@staff_member_required
def filtered(request):
    """What tier 0 rejected and why.

    This page is the whole defense against silent over-filtering. A rule that
    quietly hides good jobs looks exactly like a slow market, and the only way to
    tell the difference is to read what was thrown away.
    """
    reason = request.GET.get('reason', '')
    postings = JobPosting.objects.filter(status=JobPosting.STATUS_FILTERED)
    if reason:
        postings = postings.filter(filter_reason__startswith=reason)

    # Group by the reason's prefix -- the text after ':' is per-posting detail.
    buckets = {}
    for row in (JobPosting.objects.filter(status=JobPosting.STATUS_FILTERED)
                .values_list('filter_reason', flat=True)):
        buckets[(row or '').split(':')[0]] = buckets.get((row or '').split(':')[0], 0) + 1

    return render(request, 'jobs/filtered.html', {
        'postings': postings.select_related('source').order_by('-discovered_at')[:200],
        'buckets': sorted(buckets.items(), key=lambda kv: -kv[1]),
        'reason': reason,
        'total': postings.count(),
    })


@staff_member_required
@require_POST
def set_status(request, pk):
    """Advance a posting's status and record it on the timeline."""
    posting = get_object_or_404(JobPosting, pk=pk)
    status = request.POST.get('status', '')
    valid = {value for value, _label in JobPosting.STATUS_CHOICES}
    if status not in valid:
        return JsonResponse({'error': f'unknown status {status!r}'}, status=400)

    posting.status = status
    posting.save(update_fields=['status'])
    ApplicationEvent.objects.create(posting=posting, status=status,
                                    note=request.POST.get('note', '')[:2000])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'status': status})
    return redirect(request.POST.get('next') or 'jobs:detail', pk=pk)


@staff_member_required
@require_POST
def prep(request, pk):
    """Kick off tailoring and return immediately -- the page polls for the result."""
    posting = get_object_or_404(JobPosting, pk=pk)
    application = start_prep(posting, force=request.POST.get('force') == '1')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'state': application.state, 'version': application.version},
                            status=202)
    return redirect('jobs:detail', pk=pk)


@staff_member_required
def prep_status(request, pk):
    """Poll target. Deliberately tiny -- it is hit every couple of seconds."""
    posting = get_object_or_404(JobPosting, pk=pk)
    application = posting.current_application
    if application is None:
        return JsonResponse({'state': 'none'})
    state = application.state
    if state == TailoredApplication.PENDING and application.is_stale:
        state = 'stale'
    return JsonResponse({
        'state': state,
        'version': application.version,
        'error': application.error[:300],
        'stretch_claims': application.stretch_claims,
        'cost': str(application.cost_usd),
    })


@staff_member_required
def resume_pdf(request, pk):
    """Tailored resume, rendered on demand from stored JSON via resume/pdf.py."""
    posting = get_object_or_404(JobPosting, pk=pk)
    application = posting.current_application
    if application is None or application.state != TailoredApplication.READY:
        raise Http404('This job has not been prepped yet.')

    try:
        max_pages = min(3, max(1, int(request.GET.get('pages', 2))))
    except ValueError:
        max_pages = 2

    view = TailoredResumeView.from_json(application.resume_json)
    pdf = render_resume_pdf(view, max_pages=max_pages)

    response = HttpResponse(pdf, content_type='application/pdf')
    name = slugify(f'{view.name}-{posting.company}-{posting.title}')[:80] or 'resume'
    response['Content-Disposition'] = f'attachment; filename="{name}.pdf"'
    return response


@staff_member_required
def resume_docx(request, pk):
    """Same resume as .docx -- several ATS parse Word more reliably than PDF."""
    posting = get_object_or_404(JobPosting, pk=pk)
    application = posting.current_application
    if application is None or application.state != TailoredApplication.READY:
        raise Http404('This job has not been prepped yet.')

    view = TailoredResumeView.from_json(application.resume_json)
    data = render_resume_docx(view, PROFILE_LINKS)
    response = HttpResponse(
        data,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    name = slugify(f'{view.name}-{posting.company}-{posting.title}')[:80] or 'resume'
    response['Content-Disposition'] = f'attachment; filename="{name}.docx"'
    return response


@staff_member_required
def cover_pdf(request, pk):
    """Cover letter on the same letterhead as the resume."""
    posting = get_object_or_404(JobPosting, pk=pk)
    application = posting.current_application
    if application is None or application.state != TailoredApplication.READY:
        raise Http404('This job has not been prepped yet.')
    if not application.cover_letter_md.strip():
        raise Http404('No cover letter was generated for this posting.')

    view = TailoredResumeView.from_json(application.resume_json)
    pdf = render_cover_letter_pdf(view, posting, application.cover_letter_md,
                                  ApplicantProfile.active())
    response = HttpResponse(pdf, content_type='application/pdf')
    name = slugify(f'{view.name}-{posting.company}-cover-letter')[:80] or 'cover-letter'
    response['Content-Disposition'] = f'attachment; filename="{name}.pdf"'
    return response


@staff_member_required
def sources(request):
    """Source health. A board that quietly stopped returning jobs is invisible
    otherwise -- ``last_success_at`` and the failure counter make it obvious."""
    return render(request, 'jobs/sources.html', {
        # Annotation names must not collide with the 'postings' related_name.
        'sources': JobSource.objects.annotate(
            n_postings=Count('postings'),
            n_survivors=Count('postings', filter=~Q(postings__status='filtered')),
        ).order_by('-n_survivors', 'kind', 'label'),
        'now': timezone.now(),
    })
