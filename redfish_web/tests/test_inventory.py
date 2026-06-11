import pytest
from rest_framework.test import APIClient
from inventory.models import InventorySnapshot, SensorReading, LogEntry


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_fleet_dashboard_empty(client):
    resp = client.get("/api/fleet/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_fleet_dashboard_with_host(client, bmc_host, snapshot):
    resp = client.get("/api/fleet/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["host"] == "https://bmc.test"
    assert data[0]["latest_snapshot"]["health"] == "OK"


@pytest.mark.django_db
def test_snapshots_list(client, bmc_host, snapshot):
    resp = client.get(f"/api/hosts/{bmc_host.pk}/snapshots/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.django_db
def test_sensors_list_empty(client, bmc_host, snapshot):
    resp = client.get(f"/api/hosts/{bmc_host.pk}/sensors/")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.django_db
def test_sensors_list_with_data(client, bmc_host, snapshot):
    SensorReading.objects.create(snapshot=snapshot, name="Inlet Temp", reading=22.5, unit="C", status="OK")
    resp = client.get(f"/api/hosts/{bmc_host.pk}/sensors/")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["name"] == "Inlet Temp"


@pytest.mark.django_db
def test_logs_list(client, bmc_host):
    from datetime import datetime, timezone
    LogEntry.objects.create(
        host=bmc_host, entry_id="1", occurred_at=datetime.now(timezone.utc),
        severity="Warning", message="Fan speed low"
    )
    resp = client.get(f"/api/hosts/{bmc_host.pk}/logs/")
    assert resp.status_code == 200
    assert resp.json()["results"][0]["severity"] == "Warning"
