from django.contrib import admin

from .models import Participant, Payment, Session


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'created_at')
    search_fields = ('name', 'code')
    inlines = [ParticipantInline, PaymentInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'session')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('paid_by', 'amount', 'to_entity', 'to_participant', 'session', 'created_at')
