from celery import shared_task
from django.core.mail import EmailMessage



@shared_task
def send_celery_email(email, num1, num2, delay_time, trickery):
        
    sum = num1 + num2
    
    if trickery:
        trickery_string = "Sorry, the delay time must be <= int(61). This email was sent after the default delay of 60 seconds. "
    else:
        trickery_string = f"This email was sent after {delay_time} seconds via Celery. "
        
    print(f'Celery sending email to {email}')
        
    subject = 'Message from ChrisRiewaldt.com - Your Sum Calculation & My CV via Celery Task'
    message = f'ChrisRiewaldt.com celery task said: the sum of {num1} and {num2} equals {sum}. {trickery_string}Please see the download link to his CV here: \n\nhttps://chrisriewaldt.s3.amazonaws.com/website/CV/ChrisRResume.pdf \n\nThanks,\n-Chris Riewaldt'
    email_msg = EmailMessage(
        subject,
        message,
        'criewaldt@gmail.com',
        [email]
    )
    email_msg.send()