from celery import shared_task
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import os
@shared_task
def send_celery_email(email, num1, num2):
    cv_path = os.path.join(settings.STATIC_ROOT, 'ChrisR_Resume.pdf')    
    sum = num1 + num2
    subject = 'Message from ChrisRiewaldt.com - My CV via Celery Task'
    message = f'The sum of {num1} and {num2} is {sum}. Also, please see my CV attached. -Chris Riewaldt'
    email = EmailMessage(
        subject,
        message,
        'criewaldt@gmail.com',
        [email]
    )
    email.attach_file(cv_path)
    send_mail(subject, message, 'criewaldt@gmail.com', [email])