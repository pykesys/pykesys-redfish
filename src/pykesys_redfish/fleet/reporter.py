from __future__ import annotations

import csv
import json
from collections import Counter


def summarize_health(results: list[dict]) -> dict:
    """Produce a health rollup summary from a list of inventory results."""
    total = len(results)
    errors = [r for r in results if r.get("error")]
    healthy = [r for r in results if not r.get("error") and r.get("health") == "OK"]
    warning = [r for r in results if not r.get("error") and r.get("health") == "Warning"]
    critical = [r for r in results if not r.get("error") and r.get("health") == "Critical"]
    power_counts = Counter(r.get("power_state") for r in results if not r.get("error"))

    return {
        "total": total,
        "errors": len(errors),
        "health_ok": len(healthy),
        "health_warning": len(warning),
        "health_critical": len(critical),
        "power_states": dict(power_counts),
        "error_hosts": [r["host"] for r in errors],
    }


_INVENTORY_FIELDS = [
    "host",
    "id",
    "hostname",
    "manufacturer",
    "model",
    "serial_number",
    "bios_version",
    "power_state",
    "health",
    "total_memory_gib",
    "processor_count",
    "processor_model",
    "error",
]


def export_csv(results: list[dict], path: str) -> None:
    """Write inventory results to a CSV file."""
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_INVENTORY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def export_json(results: list[dict], path: str) -> None:
    """Write inventory results to a JSON file."""
    with open(path, "w") as fh:
        json.dump(results, fh, indent=2, default=str)
