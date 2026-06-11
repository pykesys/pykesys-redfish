from __future__ import annotations

import httpx
import pytest
import respx

from pykesys_redfish import RedfishClient
from pykesys_redfish.exceptions import RedfishAuthError, RedfishNotFoundError

BASE = "https://bmc.test"


def test_context_manager_connects_and_closes(mock_bmc):
    with RedfishClient(BASE, "admin", "password") as rf:
        assert rf._connected


def test_get_returns_json(mock_bmc):
    with RedfishClient(BASE, "admin", "password") as rf:
        data = rf.get("/redfish/v1/Systems/")
        assert data["Members"][0]["@odata.id"] == "/redfish/v1/Systems/1/"


def test_raises_auth_error_on_401(mock_bmc):
    mock_bmc.get("/redfish/v1/secret/").mock(return_value=httpx.Response(401, json={"error": {"message": "Unauthorized"}}))
    with RedfishClient(BASE, "admin", "password") as rf:
        with pytest.raises(RedfishAuthError) as exc_info:
            rf.get("/redfish/v1/secret/")
    assert exc_info.value.status_code == 401


def test_raises_not_found_on_404(mock_bmc):
    mock_bmc.get("/redfish/v1/missing/").mock(return_value=httpx.Response(404, json={"error": {"message": "Not Found"}}))
    with RedfishClient(BASE, "admin", "password") as rf:
        with pytest.raises(RedfishNotFoundError):
            rf.get("/redfish/v1/missing/")


def test_basic_auth_mode(mock_bmc):
    with RedfishClient(BASE, "admin", "password", auth="basic") as rf:
        data = rf.get("/redfish/v1/Systems/")
        assert "Members" in data


def test_from_env(mock_bmc, monkeypatch):
    monkeypatch.setenv("RF_HOST", BASE)
    monkeypatch.setenv("RF_USER", "admin")
    monkeypatch.setenv("RF_PASS", "password")
    monkeypatch.setenv("RF_VERIFY_SSL", "false")
    rf = RedfishClient.from_env()
    assert rf._session.base_url == BASE
