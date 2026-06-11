import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from hosts.models import BMCHost


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_list_hosts_empty(client):
    resp = client.get("/api/hosts/")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


@pytest.mark.django_db
def test_create_host(client):
    payload = {"host": "https://bmc1.test", "username": "admin", "password": "secret"}
    resp = client.post("/api/hosts/", payload, format="json")
    assert resp.status_code == 201
    assert BMCHost.objects.count() == 1


@pytest.mark.django_db
def test_retrieve_host(client, bmc_host):
    resp = client.get(f"/api/hosts/{bmc_host.pk}/")
    assert resp.status_code == 200
    assert resp.json()["host"] == "https://bmc.test"


@pytest.mark.django_db
def test_update_host(client, bmc_host):
    resp = client.patch(f"/api/hosts/{bmc_host.pk}/", {"display_name": "Rack A"}, format="json")
    assert resp.status_code == 200
    bmc_host.refresh_from_db()
    assert bmc_host.display_name == "Rack A"


@pytest.mark.django_db
def test_delete_host(client, bmc_host):
    resp = client.delete(f"/api/hosts/{bmc_host.pk}/")
    assert resp.status_code == 204
    assert BMCHost.objects.count() == 0


@pytest.mark.django_db
def test_base_url_property(bmc_host):
    assert bmc_host.base_url == "https://bmc.test"
    bmc_host.host = "192.168.1.100"
    assert bmc_host.base_url == "https://192.168.1.100"
