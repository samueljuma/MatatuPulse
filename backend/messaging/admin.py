from django.contrib import admin

from .models import OutboundSms


@admin.register(OutboundSms)
class OutboundSmsAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "to", "provider", "status", "provider_message_id", "error")
    list_filter = ("kind", "status", "provider")
    search_fields = ("to", "provider_message_id")
    readonly_fields = [f.name for f in OutboundSms._meta.fields]
