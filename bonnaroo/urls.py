from django.urls import path
from . import views

app_name = 'bonnaroo'

urlpatterns = [
    path('', views.login_page, name='login'),
    path('map/', views.map_page, name='map'),
    path('logout/', views.logout_view, name='logout'),
    path('api/location/', views.update_location, name='update_location'),
    path('api/users/', views.all_users, name='all_users'),
]
