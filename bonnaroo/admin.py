from django.contrib import admin
from .models import SharedLocation, UserLocation


@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'lat', 'lng', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    ordering = ('-updated_at',)
    readonly_fields = ('updated_at',)


@admin.register(SharedLocation)
class SharedLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'tag', 'user', 'lat', 'lng', 'created_at')
    list_filter = ('tag', 'created_at')
    search_fields = ('name', 'user__username', 'user__first_name', 'user__last_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
