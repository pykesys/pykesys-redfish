from rest_framework import serializers
from .models import AlertRule, AlertEvent


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = [
            "id", "name", "field", "operator", "value", "severity",
            "enabled", "notify_slack_webhook", "notify_email", "created_at",
        ]


class AlertEventSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    rule_severity = serializers.CharField(source="rule.severity", read_only=True)
    host_display = serializers.CharField(source="host.__str__", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = AlertEvent
        fields = [
            "id", "rule", "rule_name", "rule_severity", "host", "host_display",
            "triggered_at", "resolved_at", "message", "notified", "is_open",
        ]
