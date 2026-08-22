from django.urls import path

from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('fetch/', views.fetch, name='fetch'),
    path('fetch/status/', views.fetch_status, name='fetch-status'),
    path('score-all/', views.score_all, name='score-all'),
    path('filtered/', views.filtered, name='filtered'),
    path('sources/', views.sources, name='sources'),
    path('job/<int:pk>/', views.detail, name='detail'),
    path('job/<int:pk>/prep/', views.prep, name='prep'),
    path('job/<int:pk>/prep/status/', views.prep_status, name='prep-status'),
    path('job/<int:pk>/status/', views.set_status, name='set-status'),
    path('job/<int:pk>/resume.pdf', views.resume_pdf, name='resume-pdf'),
    path('job/<int:pk>/resume.docx', views.resume_docx, name='resume-docx'),
    path('job/<int:pk>/cover.pdf', views.cover_pdf, name='cover-pdf'),
]
