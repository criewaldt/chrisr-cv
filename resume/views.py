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

def SendEmailView(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        num1 = int(request.POST.get('num1', 0))
        num2 = int(request.POST.get('num2', 0))

        print(email, num1, num2)
        
        send_celery_email.delay(email, num1, num2)
        
        return JsonResponse({"status": "success", "message": "Email task submitted successfully"})
    else:
        return HttpResponseRedirect('/')