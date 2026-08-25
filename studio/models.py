"""Inbound enquiries from the services page.

Saved to the database before any email is attempted. A lead is the whole point of
the page, and losing one to an SMTP hiccup is not acceptable -- the notification
failing must never take the enquiry with it.
"""
from django.db import models


class Enquiry(models.Model):
    BUDGET_CHOICES = [
        ('', 'Not sure yet'),
        ('under-5k', 'Under $5,000'),
        ('5-15k', '$5,000 - $15,000'),
        ('15-40k', '$15,000 - $40,000'),
        ('40k-plus', '$40,000+'),
        ('retainer', 'Ongoing / retainer'),
    ]
    TIMELINE_CHOICES = [
        ('', 'No fixed date'),
        ('asap', 'As soon as possible'),
        ('1-month', 'Within a month'),
        ('quarter', 'This quarter'),
        ('exploring', 'Just exploring'),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=160, blank=True, default='')
    budget = models.CharField(max_length=20, choices=BUDGET_CHOICES, blank=True, default='')
    timeline = models.CharField(max_length=20, choices=TIMELINE_CHOICES, blank=True, default='')
    message = models.TextField()

    source = models.CharField(max_length=40, blank=True, default='',
                              help_text='Which call to action the visitor used.')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    contacted = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    # Kept only for spam triage.
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        verbose_name_plural = 'enquiries'
        ordering = ['-created_at']

    def __str__(self):
        who = f'{self.name} ({self.company})' if self.company else self.name
        return f'{who} — {self.created_at:%b %d}'

    @property
    def budget_label(self):
        return dict(self.BUDGET_CHOICES).get(self.budget, 'Not sure yet')

    @property
    def timeline_label(self):
        return dict(self.TIMELINE_CHOICES).get(self.timeline, 'No fixed date')
