from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'email', 'budget', 'timeline',
                    'created_at', 'contacted')
    list_filter = ('contacted', 'budget', 'timeline', 'created_at')
    search_fields = ('name', 'email', 'company', 'message')
    readonly_fields = ('created_at', 'ip', 'user_agent', 'source')
    actions = ['mark_contacted']

    @admin.action(description='Mark as contacted')
    def mark_contacted(self, request, queryset):
        queryset.update(contacted=True)
