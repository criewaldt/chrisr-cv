from django.shortcuts import render

from rest_framework import viewsets

from .models import Resume
from .serializers import ResumeSerializer
from .permissions import IsAdminOrReadOnly

from django.http import JsonResponse


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