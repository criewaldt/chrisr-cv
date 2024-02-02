import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.templatetags.static import static
from django.shortcuts import render

from rest_framework import viewsets

from .models import Resume
from .serializers import ResumeSerializer
from .permissions import IsAdminOrReadOnly

class ResumeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ResumeSerializer
    queryset = Resume.objects.all()

    def list(self, request, *args, **kwargs):
        if 'json' in request.GET:
            return super().list(request, *args, **kwargs)
        # if 'download' in request.GET:
        #     file_path = os.path.join(settings.BASE_DIR, 'static', 'ChrisR_Resume.pdf')
        #     print(file_path)
        #     try:
        #         return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        #     except FileNotFoundError:
        #         raise Http404('The requested pdf was not found in the static folder.')
        else:
            queryset = self.filter_queryset(self.get_queryset())
            return render(request, 'index.html', {'resume': queryset})
