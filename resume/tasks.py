from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_celery_email(email, num1, num2):
    sum = num1 + num2
    subject = 'ChrisRiewaldt.com - My CV & Your Sum Result'
    message = f'The sum of {num1} and {num2} is {sum}. Also, please see my CV attached. -Chris'
    send_mail(subject, message, 'from@example.com', [email])