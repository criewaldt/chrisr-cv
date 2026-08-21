from django.shortcuts import render

from rest_framework import viewsets

from .models import Resume
from .serializers import ResumeSerializer
from .permissions import IsAdminOrReadOnly

from django.http import Http404, HttpResponse, JsonResponse
from django.utils.text import slugify

from .merge_fields import generate_cv
from .pdf import DEFAULT_MAX_PAGES, render_resume_pdf

class ResumeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ResumeSerializer
    queryset = Resume.objects.all()

    def list(self, request, *args, **kwargs):
        if 'json' in request.GET:
            return super().list(request, *args, **kwargs)
        else:
            queryset = self.filter_queryset(self.get_queryset())
            return render(request, 'index.html', {'resume': queryset})


def ResumePDFView(request):
    """Serve the stored resume data as a downloadable PDF.

    ``?pages=N`` sets the page budget the type is fitted to (1-3, default 2).
    """
    resume = Resume.objects.select_related('professional_summary').prefetch_related(
        'employment_history', 'education', 'awards', 'keywords'
    ).first()

    if resume is None:
        raise Http404('No resume has been created yet.')

    try:
        max_pages = min(3, max(1, int(request.GET.get('pages', DEFAULT_MAX_PAGES))))
    except ValueError:
        max_pages = DEFAULT_MAX_PAGES

    pdf = render_resume_pdf(resume, max_pages=max_pages)
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f'{slugify(resume.name) or "resume"}-resume.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


from .tasks import send_celery_email
from django.http import HttpResponseRedirect
from django.urls import reverse

def clean_delay_time(t):
    if isinstance(t, int) and t < 61:
        return (t, False)
    else:
        return (int(60), True)

def SendEmailView(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        num1 = request.POST.get('num1', 1336)
        num2 = request.POST.get('num2', 1)
        delay_time = int(request.POST.get('delay', 60))
        
        if not isinstance(num1, int) or not isinstance(num2, int):
            num1 = 1336
            num2 = 1
        
        print(f'Sending celery email with {num1}, {num2}, and delay of {delay_time}')
        
        clean_time, trickery = clean_delay_time(delay_time)

        send_celery_email.apply_async(args=[email, num1, num2, delay_time, trickery], countdown=clean_time)
        
        return JsonResponse({"status": "success", "message": "Email task submitted successfully"})
    else:
        return HttpResponseRedirect('/')