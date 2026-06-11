from __future__ import annotations

import logging
from datetime import datetime, timezone

from hosts.models import BMCHost
from .models import InventorySnapshot, SensorReading, LogEntry

logger = logging.getLogger(__name__)


def poll_host(host: BMCHost) -> dict:
    """Poll a single BMC host, persist a snapshot, and return a result dict."""
    from pykesys_redfish import RedfishClient, RedfishError

    try:
        with RedfishClient(
            host.base_url,
            host.username,
            host.password,
            verify_ssl=host.verify_ssl,
            timeout=20.0,
        ) as rf:
            system = rf.system()
            summary = system.summary()

            snapshot = InventorySnapshot.objects.create(
                host=host,
                power_state=summary.get("power_state") or "",
                health=summary.get("health") or "",
                bios_version=summary.get("bios_version") or "",
                model=summary.get("model") or "",
                manufacturer=summary.get("manufacturer") or "",
                serial_number=summary.get("serial_number") or "",
                hostname=summary.get("hostname") or "",
                total_memory_gib=summary.get("total_memory_gib"),
                processor_count=summary.get("processor_count"),
                processor_model=summary.get("processor_model") or "",
                raw_json=summary,
            )

            # Thermal sensors
            try:
                chassis = rf.chassis()
                for t in chassis.temperatures():
                    SensorReading.objects.create(
                        snapshot=snapshot,
                        name=t.get("Name", ""),
                        reading=t.get("ReadingCelsius"),
                        unit="C",
                        status=t.get("Status", {}).get("Health", ""),
                        upper_threshold_critical=t.get("UpperThresholdCritical"),
                    )
                for f in chassis.fans():
                    SensorReading.objects.create(
                        snapshot=snapshot,
                        name=f.get("Name", ""),
                        reading=f.get("Reading"),
                        unit=f.get("ReadingUnits", ""),
                        status=f.get("Status", {}).get("Health", ""),
                    )
            except Exception:
                pass  # sensors are best-effort

            # SEL log entries (new ones only)
            try:
                for entry in system.log_entries():
                    occurred_raw = entry.get("Created", "")
                    try:
                        occurred = datetime.fromisoformat(occurred_raw.replace("Z", "+00:00"))
                    except Exception:
                        occurred = datetime.now(timezone.utc)
                    LogEntry.objects.get_or_create(
                        host=host,
                        entry_id=str(entry.get("Id", "")),
                        defaults={
                            "occurred_at": occurred,
                            "severity": entry.get("Severity", ""),
                            "message": entry.get("Message", ""),
                            "message_id": entry.get("MessageId", ""),
                        },
                    )
            except Exception:
                pass  # logs are best-effort

        host.last_seen = datetime.now(timezone.utc)
        host.last_error = ""
        host.save(update_fields=["last_seen", "last_error"])

        return {"snapshot_id": snapshot.pk, "health": snapshot.health}

    except RedfishError as exc:
        _mark_error(host, str(exc))
        return {"error": str(exc)}
    except Exception as exc:
        _mark_error(host, str(exc))
        return {"error": str(exc)}


def _mark_error(host: BMCHost, error: str) -> None:
    host.last_error = error
    host.last_seen = datetime.now(timezone.utc)
    host.save(update_fields=["last_error", "last_seen"])
    logger.warning("Poll failed for %s: %s", host.host, error)
