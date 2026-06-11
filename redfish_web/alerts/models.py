from django.db import models
from hosts.models import BMCHost


class AlertRule(models.Model):
    FIELD_CHOICES = [
        ("health", "Health"),
        ("power_state", "Power State"),
    ]
    OP_CHOICES = [
        ("eq", "equals"),
        ("neq", "not equals"),
    ]
    SEVERITY_CHOICES = [("warning", "Warning"), ("critical", "Critical")]

    name = models.CharField(max_length=255)
    field = models.CharField(max_length=50, choices=FIELD_CHOICES)
    operator = models.CharField(max_length=10, choices=OP_CHOICES, default="eq")
    value = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="warning")
    enabled = models.BooleanField(default=True)
    notify_slack_webhook = models.URLField(blank=True)
    notify_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.field} {self.operator} {self.value})"

    def matches(self, snapshot) -> bool:
        actual = getattr(snapshot, self.field, None)
        if actual is None:
            return False
        if self.operator == "eq":
            return str(actual) == self.value
        if self.operator == "neq":
            return str(actual) != self.value
        return False


class AlertEvent(models.Model):
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name="events")
    host = models.ForeignKey(BMCHost, on_delete=models.CASCADE, related_name="alert_events")
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField()
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"[{self.rule.severity.upper()}] {self.rule.name} on {self.host}"

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None
