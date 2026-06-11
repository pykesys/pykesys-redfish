from django.contrib import admin
from .models import InventorySnapshot, SensorReading, LogEntry


@admin.register(InventorySnapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ["host", "polled_at", "power_state", "health", "bios_version"]
    list_filter = ["health", "power_state"]
    readonly_fields = ["polled_at"]


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ["host", "occurred_at", "severity", "message"]
    list_filter = ["severity"]
