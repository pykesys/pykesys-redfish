from django.contrib import admin
from .models import AlertRule, AlertEvent


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "field", "operator", "value", "severity", "enabled"]
    list_filter = ["enabled", "severity", "field"]


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ["rule", "host", "triggered_at", "resolved_at", "notified"]
    list_filter = ["rule__severity", "notified"]
    readonly_fields = ["triggered_at"]
