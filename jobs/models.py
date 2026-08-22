"""Data model for the job hunt pipeline.

Three tiers of work, and the models mirror them: every discovered posting becomes
a JobPosting, the ones that survive the free pre-filter get a JobScore, and only
the ones Chris clicks on get a TailoredApplication. Nothing here is deleted --
rejected postings keep their ``filter_reason`` so the pre-filter stays auditable.

List-ish fields use JSONField rather than ArrayField so the same migrations run on
CockroachDB (production), Postgres, and SQLite alike.
"""
from django.db import models
from django.utils import timezone


def _list():
    return []


def _dict():
    return {}


class SearchProfile(models.Model):
    """What Chris is looking for. One active row drives the whole pipeline."""

    name = models.CharField(max_length=100, default='Default search')
    is_active = models.BooleanField(default=True)

    # Tier 0 pre-filter inputs
    titles = models.JSONField(default=_list, blank=True,
                              help_text='Case-insensitive substrings; a title matching none is rejected.')
    title_exclusions = models.JSONField(default=_list, blank=True)
    locations = models.JSONField(default=_list, blank=True,
                                 help_text='Case-insensitive substrings matched against posting location.')
    remote_ok = models.BooleanField(default=True)
    remote_only = models.BooleanField(default=False)
    min_salary = models.IntegerField(
        null=True, blank=True,
        help_text='Rejects a posting only when it states a max below this. Unstated salary always passes.')
    seniority_floor = models.CharField(max_length=20, blank=True, default='')
    seniority_ceiling = models.CharField(max_length=20, blank=True, default='')

    must_have = models.JSONField(default=_list, blank=True)
    nice_to_have = models.JSONField(default=_list, blank=True)
    exclude_keywords = models.JSONField(default=_list, blank=True)
    exclude_companies = models.JSONField(default=_list, blank=True)

    # Tier 1 / display. These encode Chris's real ceiling: discovery is deliberately
    # wide, but the inbox only ever shows what he can actually act on in a day.
    min_score_to_show = models.IntegerField(default=60)
    daily_application_target = models.IntegerField(
        default=15, help_text='Applications per day the funnel aims to supply.')
    daily_inbox_size = models.IntegerField(
        default=25, help_text='How many scored jobs the inbox and digest surface per day.')
    max_triage_per_run = models.IntegerField(
        default=80,
        help_text='Safety valve. Above this, the free keyword pre-rank picks which to score.')
    tailoring_mode = models.CharField(
        max_length=20, default='maximum',
        choices=[('maximum', 'Maximum keyword optimization'),
                 ('balanced', 'Balanced'),
                 ('conservative', 'Supported claims only')],
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first()

    @classmethod
    async def aactive(cls):
        """Async twin -- the pipeline runs inside an event loop."""
        return await cls.objects.filter(is_active=True).afirst()


class ApplicantProfile(models.Model):
    """Standing answers reused across every application. Feeds the pre-drafted screener answers in the kit."""

    is_active = models.BooleanField(default=True)

    work_authorized = models.BooleanField(default=True)
    needs_sponsorship = models.BooleanField(default=False)
    salary_expectation = models.CharField(max_length=100, blank=True, default='')
    notice_period = models.CharField(max_length=100, blank=True, default='')
    willing_to_relocate = models.BooleanField(default=False)
    preferred_locations = models.JSONField(default=_list, blank=True)

    linkedin_url = models.URLField(blank=True, default='')
    github_url = models.URLField(blank=True, default='')
    portfolio_url = models.URLField(blank=True, default='')
    references_note = models.TextField(blank=True, default='')

    # EEO / demographic answers are optional on most ATS forms; stored so the kit
    # can answer consistently rather than leaving Chris to re-decide each time.
    eeo_answers = models.JSONField(default=_dict, blank=True)
    extra_answers = models.JSONField(default=_dict, blank=True,
                                     help_text='Freeform question -> answer bank the screener drafting draws from.')

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Applicant profile'

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).first()

    @classmethod
    async def aactive(cls):
        return await cls.objects.filter(is_active=True).afirst()


class JobSource(models.Model):
    """One configured adapter instance -- e.g. Greenhouse for a single company."""

    KIND_CHOICES = [
        ('greenhouse', 'Greenhouse'), ('lever', 'Lever'), ('ashby', 'Ashby'),
        ('remotive', 'Remotive'), ('arbeitnow', 'Arbeitnow'),
        ('usajobs', 'USAJobs'), ('hn_hiring', 'HN Who Is Hiring'),
        ('adzuna', 'Adzuna'), ('jsearch', 'JSearch'),
    ]
    AUTO_DISABLE_AFTER = 5

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    label = models.CharField(max_length=120, blank=True, default='')
    config = models.JSONField(default=_dict, blank=True,
                              help_text='Adapter config (company slug, query params). Never secrets -- those come from env.')
    enabled = models.BooleanField(default=True)

    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    consecutive_failures = models.IntegerField(default=0)

    class Meta:
        ordering = ['kind', 'label']

    def __str__(self):
        return self.label or f'{self.get_kind_display()} ({self.config})'

    def record_success(self, save=True):
        now = timezone.now()
        self.last_run_at = now
        self.last_success_at = now
        self.last_error = ''
        self.consecutive_failures = 0
        if save:
            self.save(update_fields=['last_run_at', 'last_success_at',
                                     'last_error', 'consecutive_failures'])

    def record_failure(self, error, save=True):
        """Fail soft. Auto-disable once a source has been broken long enough to be noise."""
        self.last_run_at = timezone.now()
        self.last_error = str(error)[:2000]
        self.consecutive_failures += 1
        fields = ['last_run_at', 'last_error', 'consecutive_failures']
        if self.consecutive_failures >= self.AUTO_DISABLE_AFTER:
            self.enabled = False
            fields.append('enabled')
        if save:
            self.save(update_fields=fields)


class JobPosting(models.Model):
    """A discovered posting. Deduped across sources by ``dedupe_key``."""

    STATUS_NEW = 'new'
    STATUS_FILTERED = 'filtered'
    STATUS_SCORED = 'scored'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_FILTERED, 'Filtered out'),
        (STATUS_SCORED, 'Scored'),
        ('shortlisted', 'Shortlisted'),
        ('prepped', 'Prepped'),
        ('applied', 'Applied'),
        ('interviewing', 'Interviewing'),
        ('offer', 'Offer'),
        ('rejected', 'Rejected'),
        ('dismissed', 'Dismissed'),
        ('closed', 'Closed'),
    ]
    # Statuses that mean Chris has acted on this posting -- excluded from bulk dismiss.
    ACTIVE_STATUSES = ('shortlisted', 'prepped', 'applied', 'interviewing', 'offer')

    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name='postings')
    external_id = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    alt_urls = models.JSONField(default=_list, blank=True,
                                help_text='Other boards listing the same role, found during dedupe.')
    dedupe_key = models.CharField(max_length=64, unique=True, db_index=True)

    title = models.CharField(max_length=300)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, default='')
    is_remote = models.BooleanField(default=False)
    salary_min = models.IntegerField(null=True, blank=True)
    salary_max = models.IntegerField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    description_html = models.TextField(blank=True, default='')
    description_text = models.TextField(blank=True, default='')
    raw = models.JSONField(default=_dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_NEW, db_index=True)
    filter_reason = models.CharField(max_length=200, blank=True, default='',
                                     help_text='Why tier 0 rejected this. Keeps the pre-filter auditable.')
    discovered_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = [('source', 'external_id')]
        ordering = ['-discovered_at']
        indexes = [models.Index(fields=['status', '-discovered_at'])]

    def __str__(self):
        return f'{self.title} @ {self.company}'

    @property
    def salary_display(self):
        if self.salary_min and self.salary_max:
            return f'${self.salary_min:,} - ${self.salary_max:,}'
        if self.salary_max:
            return f'up to ${self.salary_max:,}'
        if self.salary_min:
            return f'${self.salary_min:,}+'
        return ''

    @property
    def current_application(self):
        """Latest tailoring attempt, whatever its state."""
        return self.applications.order_by('-version').first()


class JobScore(models.Model):
    """Tier 1 triage output. Only exists for postings that survived the pre-filter."""

    posting = models.OneToOneField(JobPosting, on_delete=models.CASCADE, related_name='score')
    fit_score = models.IntegerField(db_index=True)
    verdict = models.CharField(max_length=20, blank=True, default='')
    reasoning = models.TextField(blank=True, default='')
    matched_keywords = models.JSONField(default=_list, blank=True)
    missing_keywords = models.JSONField(default=_list, blank=True)
    red_flags = models.JSONField(default=_list, blank=True)

    model_used = models.CharField(max_length=60, blank=True, default='')
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.fit_score} - {self.posting}'


class TailoredApplication(models.Model):
    """Tier 2 output. Only created when Chris clicks Prep, which is the whole cost story.

    ``state`` tracks the background thread that generates it: a row appears as
    ``pending`` immediately so the page has something to poll.
    """

    PENDING, READY, FAILED = 'pending', 'ready', 'failed'
    STATE_CHOICES = [(PENDING, 'Pending'), (READY, 'Ready'), (FAILED, 'Failed')]
    # A dyno restart kills in-flight threads; anything pending longer than this is stale.
    STALE_AFTER_SECONDS = 300

    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    version = models.IntegerField(default=1)

    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=PENDING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')

    resume_json = models.JSONField(default=_dict, blank=True)
    cover_letter_md = models.TextField(blank=True, default='')
    # The letter exactly as generated, kept so editing is never a one-way door --
    # reverting costs nothing rather than another tailoring call.
    cover_letter_original = models.TextField(blank=True, default='')
    cover_letter_edited_at = models.DateTimeField(null=True, blank=True)
    cover_letter_needed = models.BooleanField(default=True)
    screener_answers = models.JSONField(default=_dict, blank=True)
    ats_keywords_used = models.JSONField(default=_list, blank=True)
    stretch_claims = models.JSONField(default=_list, blank=True,
                                      help_text='Claims beyond the master resume. Surfaced as "Be ready to defend".')

    model_used = models.CharField(max_length=60, blank=True, default='')
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    class Meta:
        unique_together = [('posting', 'version')]
        ordering = ['-version']

    def __str__(self):
        return f'v{self.version} {self.get_state_display()} - {self.posting}'

    @property
    def cover_letter_is_edited(self):
        return bool(self.cover_letter_edited_at)

    @property
    def can_revert_cover_letter(self):
        return bool(self.cover_letter_original
                    and self.cover_letter_original != self.cover_letter_md)

    @property
    def is_stale(self):
        """Pending far too long means the thread died with its dyno."""
        if self.state != self.PENDING:
            return False
        return (timezone.now() - self.started_at).total_seconds() > self.STALE_AFTER_SECONDS


class ApplicationEvent(models.Model):
    """Status timeline. 'Applied since last email' reads off this."""

    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True, default='')
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.posting} -> {self.status}'


class RunLog(models.Model):
    """One row per scheduled cycle."""

    slot = models.CharField(max_length=20)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    sources_run = models.IntegerField(default=0)
    found = models.IntegerField(default=0)
    new = models.IntegerField(default=0)
    filtered = models.IntegerField(default=0)
    scored = models.IntegerField(default=0)
    errors = models.JSONField(default=_list, blank=True)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.slot} @ {self.started_at:%Y-%m-%d %H:%M}'


class DigestSend(models.Model):
    """One row per email. Defines the 'since the previous email' window.

    The window starts at the last *actual* send rather than a fixed clock time, so a
    skipped or failed digest rolls its contents into the next one instead of dropping them.
    """

    slot = models.CharField(max_length=20)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    new_job_count = models.IntegerField(default=0)
    applied_count = models.IntegerField(default=0)
    skipped = models.BooleanField(default=False)
    skip_reason = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        state = 'skipped' if self.skipped else 'sent'
        return f'{self.slot} {state} @ {self.sent_at:%Y-%m-%d %H:%M}'
