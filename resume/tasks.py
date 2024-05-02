from celery import shared_task
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import os
@shared_task
def send_celery_email(email, num1, num2):
    cv_path = os.path.join(settings.BASE_DIR, 'static', 'ChrisR_Resume.pdf')
        
    sum = num1 + num2
    subject = 'Message from ChrisRiewaldt.com - Your Sum Calculation & My CV via Celery Task'
    message = f'ChrisRiewaldt.com celery task said: the sum of {num1} and {num2} equals {sum}. Also, please see his CV attached. \n\nThanks,\n-Chris Riewaldt'
    email = EmailMessage(
        subject,
        message,
        'criewaldt@gmail.com',
        [email]
    )
    email.attach_file(cv_path)
    send_mail(subject, message, 'criewaldt@gmail.com', [email])