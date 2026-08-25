"""Enquiry form with dependency-free spam handling.

No captcha: it costs conversions and adds a third-party dependency for a page that
will see a handful of submissions a week. A honeypot plus a minimum time-on-page
stops naive bots, and anything that gets through is one admin click to delete.
"""
import time

from django import forms

from .models import Enquiry

# Bots fill forms instantly; a human cannot read the page and type this fast.
MIN_SECONDS_ON_PAGE = 3

# A genuine enquiry is a few paragraphs. The model field is a TextField, so without
# a cap a single request can write an arbitrarily large row.
MAX_MESSAGE_CHARS = 4000


class EnquiryForm(forms.ModelForm):
    # Named innocuously so a bot is tempted to fill it. Hidden from real users in CSS
    # and from screen readers via aria-hidden.
    website = forms.CharField(required=False, widget=forms.HiddenInput())
    loaded_at = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Enquiry
        fields = ['name', 'email', 'company', 'budget', 'timeline', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Your name', 'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@company.com',
                                             'autocomplete': 'email'}),
            'company': forms.TextInput(attrs={'placeholder': 'Company (optional)',
                                              'autocomplete': 'organization'}),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': "What is the problem costing you? Rough detail is fine — "
                               "what breaks, who it affects, and what it would be worth to fix.",
            }),
        }
        labels = {'message': 'What are you trying to fix?'}

    def clean_message(self):
        message = (self.cleaned_data.get('message') or '').strip()
        if len(message) > MAX_MESSAGE_CHARS:
            raise forms.ValidationError(
                f'Please keep this under {MAX_MESSAGE_CHARS:,} characters — '
                'a few paragraphs is plenty.')
        return message

    def clean_name(self):
        # Newlines here would land in an email Subject header, which Django rejects
        # outright -- meaning a legitimate-but-odd name would silently cost the
        # notification. Collapse whitespace instead of failing.
        return ' '.join((self.cleaned_data.get('name') or '').split())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['budget'].required = False
        self.fields['timeline'].required = False
        self.fields['company'].required = False

    @property
    def looks_like_spam(self):
        """True when the submission trips either bot check.

        Deliberately separate from validation: the view accepts these and silently
        discards them, so a bot sees success and does not retune.
        """
        if self.data.get('website'):
            return True
        try:
            elapsed = time.time() - float(self.data.get('loaded_at') or 0)
        except (TypeError, ValueError):
            return False
        return 0 < elapsed < MIN_SECONDS_ON_PAGE
