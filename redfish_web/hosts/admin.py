from django.contrib import admin
from .models import BMCHost


@admin.register(BMCHost)
class BMCHostAdmin(admin.ModelAdmin):
    list_display = ["host", "display_name", "enabled", "last_seen", "last_error"]
    list_filter = ["enabled", "verify_ssl"]
    search_fields = ["host", "display_name"]
    readonly_fields = ["last_seen", "last_error", "created_at", "updated_at"]
