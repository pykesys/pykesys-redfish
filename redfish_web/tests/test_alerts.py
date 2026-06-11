import pytest
from rest_framework.test import APIClient
from alerts.models import AlertRule, AlertEvent
from datetime import datetime, timezone


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def rule(db):
    return AlertRule.objects.create(
        name="Health Critical",
        field="health",
        operator="eq",
        value="Critical",
        severity="critical",
    )


@pytest.mark.django_db
def test_create_rule(client):
    payload = {"name": "Power Off", "field": "power_state", "operator": "eq", "value": "Off", "severity": "warning"}
    resp = client.post("/api/alerts/rules/", payload, format="json")
    assert resp.status_code == 201
    assert AlertRule.objects.count() == 1


@pytest.mark.django_db
def test_list_rules(client, rule):
    resp = client.get("/api/alerts/rules/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.django_db
def test_rule_matches_eq(rule, snapshot):
    snapshot.health = "Critical"
    assert rule.matches(snapshot) is True
    snapshot.health = "OK"
    assert rule.matches(snapshot) is False


@pytest.mark.django_db
def test_rule_matches_neq(db, snapshot):
    rule = AlertRule.objects.create(
        name="Not OK", field="health", operator="neq", value="OK", severity="warning"
    )
    snapshot.health = "Critical"
    assert rule.matches(snapshot) is True
    snapshot.health = "OK"
    assert rule.matches(snapshot) is False


@pytest.mark.django_db
def test_alert_event_creation(client, rule, bmc_host, snapshot):
    from alerts.notifications import evaluate_rules
    snapshot.health = "Critical"
    snapshot.save()
    evaluate_rules(snapshot)
    assert AlertEvent.objects.filter(rule=rule, host=bmc_host).count() == 1


@pytest.mark.django_db
def test_alert_event_resolve(client, rule, bmc_host):
    event = AlertEvent.objects.create(
        rule=rule, host=bmc_host, message="health is Critical"
    )
    resp = client.post(f"/api/alerts/events/{event.pk}/resolve/")
    assert resp.status_code == 200
    event.refresh_from_db()
    assert event.resolved_at is not None


@pytest.mark.django_db
def test_alert_event_no_duplicate(rule, bmc_host, snapshot):
    from alerts.notifications import evaluate_rules
    snapshot.health = "Critical"
    snapshot.save()
    evaluate_rules(snapshot)
    evaluate_rules(snapshot)
    assert AlertEvent.objects.filter(rule=rule, host=bmc_host, resolved_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_list_open_events(client, rule, bmc_host, snapshot):
    snapshot.health = "Critical"
    snapshot.save()
    from alerts.notifications import evaluate_rules
    evaluate_rules(snapshot)
    resp = client.get("/api/alerts/events/?open=true")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
