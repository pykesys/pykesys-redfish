"""Management command: register emulator nodes as BMCHost rows.

Reads EMULATOR_URL and EMULATOR_NUM_NODES from the environment.
Idempotent — skips nodes that already exist.

Usage:
    python manage.py init_emulator_hosts
    EMULATOR_URL=http://emulator:8888 EMULATOR_NUM_NODES=10 python manage.py init_emulator_hosts
"""

import os

from django.core.management.base import BaseCommand

from hosts.models import BMCHost


class Command(BaseCommand):
    help = "Register emulator BMC nodes as BMCHost records"

    def add_arguments(self, parser):
        parser.add_argument("--url", default=None, help="Emulator base URL (overrides EMULATOR_URL env var)")
        parser.add_argument("--nodes", type=int, default=None, help="Number of nodes (overrides EMULATOR_NUM_NODES)")
        parser.add_argument("--user", default=None, help="Admin username (overrides EMULATOR_ADMIN_USER)")
        parser.add_argument("--password", default=None, help="Admin password (overrides EMULATOR_ADMIN_PASS)")

    def handle(self, *args, **options):
        base_url = options["url"] or os.environ.get("EMULATOR_URL", "")
        if not base_url:
            self.stdout.write(self.style.WARNING("EMULATOR_URL not set — skipping emulator host init"))
            return

        num_nodes = options["nodes"] or int(os.environ.get("EMULATOR_NUM_NODES", "10"))
        username = options["user"] or os.environ.get("EMULATOR_ADMIN_USER", "admin")
        password = options["password"] or os.environ.get("EMULATOR_ADMIN_PASS", "redfish")

        base_url = base_url.rstrip("/")
        created = 0
        skipped = 0

        for i in range(1, num_nodes + 1):
            host_url = f"{base_url}/bmc/{i}"
            _, was_created = BMCHost.objects.get_or_create(
                host=host_url,
                defaults={
                    "display_name": f"Sim Node {i:02d}",
                    "username": username,
                    "password": password,
                    "verify_ssl": False,
                    "enabled": True,
                    "poll_interval": 60,
                    "tags": ["emulator", f"node-{i}"],
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Emulator hosts: {created} created, {skipped} already existed "
                f"({num_nodes} total, base={base_url})"
            )
        )
