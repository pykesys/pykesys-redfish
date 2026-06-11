from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def run_poll_cycle() -> None:
    """Poll all enabled hosts that are due for a check."""
    import django
    django.setup()

    from hosts.models import BMCHost
    from inventory.tasks import poll_host
    from alerts.notifications import evaluate_rules
    from inventory.models import InventorySnapshot

    now = datetime.now(timezone.utc)
    hosts = BMCHost.objects.filter(enabled=True)

    for host in hosts:
        if host.last_seen:
            next_poll = host.last_seen + timedelta(seconds=host.poll_interval)
            if now < next_poll:
                continue

        logger.info("Polling %s", host.host)
        result = poll_host(host)
        if result.get("snapshot_id"):
            try:
                snapshot = InventorySnapshot.objects.get(pk=result["snapshot_id"])
                evaluate_rules(snapshot)
            except Exception as exc:
                logger.warning("Alert evaluation failed for %s: %s", host.host, exc)
