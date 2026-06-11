from rest_framework import serializers
from .models import InventorySnapshot, SensorReading, LogEntry


class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorReading
        fields = ["id", "name", "reading", "unit", "status", "upper_threshold_critical"]


class InventorySnapshotSerializer(serializers.ModelSerializer):
    sensors = SensorReadingSerializer(many=True, read_only=True)

    class Meta:
        model = InventorySnapshot
        fields = [
            "id", "host", "polled_at", "power_state", "health",
            "bios_version", "model", "manufacturer", "serial_number",
            "hostname", "total_memory_gib", "processor_count", "processor_model",
            "sensors",
        ]


class InventorySnapshotSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = InventorySnapshot
        fields = [
            "id", "polled_at", "power_state", "health",
            "bios_version", "model", "manufacturer", "serial_number",
            "hostname", "total_memory_gib", "processor_count", "processor_model",
        ]


class LogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LogEntry
        fields = ["id", "entry_id", "occurred_at", "severity", "message", "message_id"]
