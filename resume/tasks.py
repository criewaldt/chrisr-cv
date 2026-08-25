"""No Celery tasks are defined for this app.

``send_celery_email`` lived here and was reachable from an unauthenticated
``/send-email/`` endpoint that accepted an arbitrary recipient address. It was a
demo, it had no callers, and with a broker configured it would have been an open
mail relay sending from the site's own Gmail account. Both were removed.
"""
