from django.contrib import admin

from .models import Alert, Event, Report, Vote


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "sender_phone", "raw_text", "type", "route", "is_spam", "spam_reason", "event")
    list_filter = ("source", "is_spam", "type")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "subtype", "route", "stage", "sacco", "fare", "status", "reporter_count", "first_seen", "verified_at")
    list_filter = ("status", "type")


admin.site.register(Vote)
admin.site.register(Alert)
