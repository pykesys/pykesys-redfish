from __future__ import annotations

import logging
import requests
from datetime import timezone, datetime

from .models import AlertRule, AlertEvent

logger = logging.getLogger(__name__)


def evaluate_rules(snapshot) -> None:
    """Check all enabled alert rules against a freshly-stored snapshot."""
    rules = AlertRule.objects.filter(enabled=True)
    for rule in rules:
        if rule.matches(snapshot):
            _ensure_open_event(rule, snapshot.host, snapshot)
        else:
            _resolve_open_events(rule, snapshot.host)


def _ensure_open_event(rule: AlertRule, host, snapshot) -> None:
    open_event = AlertEvent.objects.filter(rule=rule, host=host, resolved_at__isnull=True).first()
    if open_event:
        return
    msg = f"{rule.field} is {getattr(snapshot, rule.field)} (rule: {rule.field} {rule.operator} {rule.value})"
    event = AlertEvent.objects.create(rule=rule, host=host, message=msg)
    dispatch(event)


def _resolve_open_events(rule: AlertRule, host) -> None:
    AlertEvent.objects.filter(rule=rule, host=host, resolved_at__isnull=True).update(
        resolved_at=datetime.now(timezone.utc)
    )


def dispatch(event: AlertEvent) -> None:
    """Send notifications for an alert event."""
    rule = event.rule
    text = f"[{rule.severity.upper()}] {rule.name} — {event.host}: {event.message}"

    if rule.notify_slack_webhook:
        try:
            requests.post(rule.notify_slack_webhook, json={"text": text}, timeout=10)
        except Exception as exc:
            logger.warning("Slack notification failed: %s", exc)

    event.notified = True
    event.save(update_fields=["notified"])
