web: gunicorn chrisr.wsgi --log-file -
worker: celery -A chrisr worker -l INFO -E --pool=solo