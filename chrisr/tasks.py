from chrisr.celery import app
from celery import shared_task
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist
from resume.models import Resume

@shared_task
def send_subscription_alert(to, _from):
    pass