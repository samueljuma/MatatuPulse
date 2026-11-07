from django.contrib import admin

from .models import OtpCode, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "is_staff", "created_at")
    search_fields = ("phone",)
    filter_horizontal = ("subscriptions",)


admin.site.register(OtpCode)
