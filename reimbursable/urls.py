from django.urls import path

from . import views

app_name = 'reimbursable'

urlpatterns = [
    path('', views.create_session, name='create_session'),
    path('<str:code>/', views.session_detail, name='session_detail'),
    path('<str:code>/add-payment/', views.add_payment, name='add_payment'),
    path('<str:code>/delete-payment/<int:payment_id>/', views.delete_payment, name='delete_payment'),
    path('<str:code>/add-participant/', views.add_participant, name='add_participant'),
    path('<str:code>/settlements/', views.get_settlements, name='get_settlements'),
]
