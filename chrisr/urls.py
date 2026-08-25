"""
URL configuration for chrisr project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from resume.views import ResumePDFView, ResumeViewSet, SendEmailView

urlpatterns = [
    path('admin/', admin.site.urls),

    # The services page is the front door; the CV lives at /cv/.
    path('', include('studio.urls')),
    path('cv/', ResumeViewSet.as_view({'get': 'list'}), name='resume_viewset'),
    path('resume.pdf', ResumePDFView, name='resume-pdf'),
    path('send-email/', SendEmailView, name='send-email'),

    # /dev/ was the services page while it was being built -- keep shared links working.
    path('dev/', RedirectView.as_view(pattern_name='studio:landing', permanent=False)),

    path('bonnaroo/', include('bonnaroo.urls')),
    path('reimbursable/', include('reimbursable.urls')),
    path('jobs/', include('jobs.urls')),
    path('social/', include('social_django.urls', namespace='social')),
]
