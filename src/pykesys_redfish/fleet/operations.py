from __future__ import annotations

from ..client import RedfishClient


def power_reset(rf: RedfishClient, host: str, reset_type: str) -> dict:
    """Send a power reset to a single BMC host."""
    rf.system().reset(reset_type)
    return {"host": host, "action": "reset", "reset_type": reset_type, "status": "sent"}
