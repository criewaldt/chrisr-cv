from django.contrib import admin

from .models import (ApplicantProfile, ApplicationEvent, DigestSend, JobPosting,
                     JobScore, JobSource, RunLog, SearchProfile, TailoredApplication)


@admin.register(SearchProfile)
class SearchProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'min_salary', 'min_score_to_show', 'tailoring_mode')


@admin.register(ApplicantProfile)
class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'is_active', 'salary_expectation', 'notice_period')


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'kind', 'enabled', 'last_success_at',
                    'consecutive_failures', 'last_error')
    list_filter = ('kind', 'enabled')
    actions = ['reenable']

    @admin.action(description='Re-enable and clear failure count')
    def reenable(self, request, queryset):
        queryset.update(enabled=True, consecutive_failures=0, last_error='')


class JobScoreInline(admin.StackedInline):
    model = JobScore
    extra = 0


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'status', 'filter_reason', 'discovered_at')
    list_filter = ('status', 'is_remote', 'source__kind')
    search_fields = ('title', 'company', 'description_text')
    date_hierarchy = 'discovered_at'
    inlines = [JobScoreInline]


@admin.register(JobScore)
class JobScoreAdmin(admin.ModelAdmin):
    list_display = ('posting', 'fit_score', 'verdict', 'model_used', 'cost_usd')
    list_filter = ('verdict', 'model_used')


@admin.register(TailoredApplication)
class TailoredApplicationAdmin(admin.ModelAdmin):
    list_display = ('posting', 'version', 'state', 'started_at', 'finished_at', 'cost_usd')
    list_filter = ('state',)


@admin.register(ApplicationEvent)
class ApplicationEventAdmin(admin.ModelAdmin):
    list_display = ('posting', 'status', 'occurred_at')
    list_filter = ('status',)


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ('slot', 'started_at', 'finished_at', 'found', 'new',
                    'filtered', 'scored', 'cost_usd')
    list_filter = ('slot',)


@admin.register(DigestSend)
class DigestSendAdmin(admin.ModelAdmin):
    list_display = ('slot', 'sent_at', 'new_job_count', 'applied_count', 'skipped')
    list_filter = ('slot', 'skipped')
