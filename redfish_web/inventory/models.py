from django.db import models
from hosts.models import BMCHost


class InventorySnapshot(models.Model):
    host = models.ForeignKey(BMCHost, on_delete=models.CASCADE, related_name="snapshots")
    polled_at = models.DateTimeField(auto_now_add=True, db_index=True)
    power_state = models.CharField(max_length=50, blank=True)
    health = models.CharField(max_length=50, blank=True)
    bios_version = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=255, blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    serial_number = models.CharField(max_length=255, blank=True)
    hostname = models.CharField(max_length=255, blank=True)
    total_memory_gib = models.FloatField(null=True, blank=True)
    processor_count = models.IntegerField(null=True, blank=True)
    processor_model = models.CharField(max_length=255, blank=True)
    raw_json = models.JSONField(default=dict)

    class Meta:
        ordering = ["-polled_at"]

    def __str__(self):
        return f"{self.host} @ {self.polled_at}"


class SensorReading(models.Model):
    snapshot = models.ForeignKey(InventorySnapshot, on_delete=models.CASCADE, related_name="sensors")
    name = models.CharField(max_length=255)
    reading = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, blank=True)
    upper_threshold_critical = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}: {self.reading} {self.unit}"


class LogEntry(models.Model):
    SEVERITY_CHOICES = [("OK", "OK"), ("Warning", "Warning"), ("Critical", "Critical")]

    host = models.ForeignKey(BMCHost, on_delete=models.CASCADE, related_name="log_entries")
    entry_id = models.CharField(max_length=100)
    occurred_at = models.DateTimeField(db_index=True)
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES, blank=True)
    message = models.TextField(blank=True)
    message_id = models.CharField(max_length=255, blank=True)
    created_in_db = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        unique_together = [("host", "entry_id")]

    def __str__(self):
        return f"[{self.severity}] {self.host}: {self.message[:80]}"
