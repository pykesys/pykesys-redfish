from __future__ import annotations

import httpx
import pytest
import respx

from pykesys_redfish.fleet import FleetManager, summarize_health, export_csv, export_json

BASE1 = "https://bmc1.test"
BASE2 = "https://bmc2.test"


def _setup_bmc(router, base, power_state="On", health="OK"):
    router.post(f"{base}/redfish/v1/SessionService/Sessions/").mock(
        return_value=httpx.Response(
            201,
            json={"@odata.id": "/redfish/v1/SessionService/Sessions/1"},
            headers={"X-Auth-Token": "tok", "Location": "/redfish/v1/SessionService/Sessions/1"},
        )
    )
    router.delete(f"{base}/redfish/v1/SessionService/Sessions/1").mock(
        return_value=httpx.Response(204)
    )
    router.get(f"{base}/redfish/v1/Systems/").mock(
        return_value=httpx.Response(
            200, json={"Members": [{"@odata.id": "/redfish/v1/Systems/1/"}]}
        )
    )
    router.get(f"{base}/redfish/v1/Systems/1/").mock(
        return_value=httpx.Response(
            200,
            json={
                "Id": "1",
                "HostName": f"server-{base.split('//')[1]}",
                "SerialNumber": "SN001",
                "Model": "TestModel",
                "Manufacturer": "TestVendor",
                "BiosVersion": "1.0",
                "PowerState": power_state,
                "Status": {"Health": health},
                "MemorySummary": {"TotalSystemMemoryGiB": 128},
                "ProcessorSummary": {"Count": 1, "Model": "TestCPU"},
            },
        )
    )


def test_collect_inventory():
    with respx.mock(assert_all_called=False) as router:
        _setup_bmc(router, BASE1)
        _setup_bmc(router, BASE2, power_state="Off", health="Warning")

        fm = FleetManager(
            hosts=[BASE1, BASE2],
            username="admin",
            password="password",
            verify_ssl=False,
        )
        results = fm.collect_inventory()

    assert len(results) == 2
    hosts = {r["host"] for r in results}
    assert BASE1 in hosts
    assert BASE2 in hosts


def test_health_summary():
    results = [
        {"host": "a", "health": "OK", "power_state": "On"},
        {"host": "b", "health": "Warning", "power_state": "On"},
        {"host": "c", "health": "Critical", "power_state": "Off"},
        {"host": "d", "error": "timeout"},
    ]
    summary = summarize_health(results)
    assert summary["total"] == 4
    assert summary["health_ok"] == 1
    assert summary["health_warning"] == 1
    assert summary["health_critical"] == 1
    assert summary["errors"] == 1


def test_export_csv(tmp_path):
    results = [{"host": "bmc1", "hostname": "srv1", "model": "M1", "health": "OK", "power_state": "On"}]
    path = str(tmp_path / "inventory.csv")
    export_csv(results, path)
    content = open(path).read()
    assert "bmc1" in content
    assert "host" in content


def test_export_json(tmp_path):
    import json

    results = [{"host": "bmc1", "health": "OK"}]
    path = str(tmp_path / "inventory.json")
    export_json(results, path)
    data = json.load(open(path))
    assert data[0]["host"] == "bmc1"


def test_fleet_error_isolation():
    with respx.mock(assert_all_called=False) as router:
        _setup_bmc(router, BASE1)
        # BASE2 will fail — no routes registered for it
        router.get(f"{BASE2}/redfish/v1/Systems/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        router.post(f"{BASE2}/redfish/v1/SessionService/Sessions/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        fm = FleetManager(
            hosts=[BASE1, BASE2],
            username="admin",
            password="password",
            verify_ssl=False,
        )
        results = fm.collect_inventory()

    errors = [r for r in results if r.get("error")]
    successes = [r for r in results if not r.get("error")]
    assert len(errors) == 1
    assert len(successes) == 1
