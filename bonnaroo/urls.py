from django.urls import path
from . import views

app_name = 'bonnaroo'

urlpatterns = [
    path('', views.login_page, name='login'),
    path('map/', views.map_page, name='map'),
    path('account/', views.account_page, name='account'),
    path('account/name/', views.update_name, name='update_name'),
    path('account/delete/', views.delete_account, name='delete_account'),
    path('logout/', views.logout_view, name='logout'),
    path('api/location/', views.update_location, name='update_location'),
    path('api/users/', views.all_users, name='all_users'),
    path('api/pins/', views.pins, name='pins'),
    path('api/pins/<int:pin_id>/delete/', views.delete_pin, name='delete_pin'),
]
