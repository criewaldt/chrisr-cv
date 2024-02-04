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
        else:
            queryset = self.filter_queryset(self.get_queryset())
            return render(request, 'index.html', {'resume': queryset})
