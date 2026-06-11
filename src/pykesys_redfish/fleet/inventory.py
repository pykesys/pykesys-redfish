from __future__ import annotations

from ..client import RedfishClient


def collect_system_inventory(rf: RedfishClient, host: str) -> dict:
    """Collect a system inventory dict for a single BMC host."""
    summary = rf.system().summary()
    summary["host"] = host
    return summary
