from django.contrib import admin
from .models import Award, Resume, ProfessionalSummary, EmploymentHistory, Education

# Optional: Custom admin interfaces
class ProfessionalSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'summary', 'highlights')

class EmploymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('job_title', 'company_name', 'start_date', 'end_date', 'is_current')

class ResumeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'current_title', 'desired_title')
    filter_horizontal = ('employment_history',)

class AwardAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

class EducationAdmin(admin.ModelAdmin):
    list_display = ('degree', 'school', 'time')

# Register your models here
admin.site.register(ProfessionalSummary, ProfessionalSummaryAdmin)
admin.site.register(EmploymentHistory, EmploymentHistoryAdmin)
admin.site.register(Resume, ResumeAdmin)
admin.site.register(Award, AwardAdmin)
admin.site.register(Education, EducationAdmin)
