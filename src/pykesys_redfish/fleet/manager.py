from __future__ import annotations

import concurrent.futures
from typing import Callable

from ..client import RedfishClient


class FleetManager:
    """Manages concurrent Redfish operations across a fleet of BMCs.

    Each operation spawns one thread per host. Workers are isolated —
    each gets its own RedfishClient instance with its own session.

    Usage::

        fm = FleetManager(
            hosts=["bmc-a1.mgmt", "bmc-a2.mgmt"],
            username="admin",
            password="password",
        )
        inventory = fm.collect_inventory()
        fm.power_all("GracefulShutdown")
    """

    def __init__(
        self,
        hosts: list[str],
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        max_workers: int = 16,
        base_url_scheme: str = "https",
    ):
        self.hosts = hosts
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.max_workers = max_workers
        self.scheme = base_url_scheme

    def _make_client(self, host: str) -> RedfishClient:
        url = host if host.startswith("http") else f"{self.scheme}://{host}"
        return RedfishClient(
            base_url=url,
            username=self.username,
            password=self.password,
            verify_ssl=self.verify_ssl,
            timeout=self.timeout,
        )

    def _run_on_host(self, host: str, fn: Callable[[RedfishClient, str], dict]) -> dict:
        try:
            with self._make_client(host) as rf:
                return fn(rf, host)
        except Exception as exc:
            return {"host": host, "error": str(exc)}

    def run(self, fn: Callable[[RedfishClient, str], dict]) -> list[dict]:
        """Execute fn(client, host) concurrently across all hosts.

        Returns a list of result dicts, one per host. Failed hosts
        include an "error" key.
        """
        workers = min(self.max_workers, len(self.hosts))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._run_on_host, host, fn): host for host in self.hosts}
            results = []
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
        return results

    def collect_inventory(self) -> list[dict]:
        from .inventory import collect_system_inventory
        return self.run(collect_system_inventory)

    def power_all(self, reset_type: str) -> list[dict]:
        from .operations import power_reset
        return self.run(lambda rf, host: power_reset(rf, host, reset_type))

    def health_summary(self) -> dict:
        from .reporter import summarize_health
        results = self.collect_inventory()
        return summarize_health(results)

    def export_csv(self, results: list[dict], path: str) -> None:
        from .reporter import export_csv
        export_csv(results, path)

    def export_json(self, results: list[dict], path: str) -> None:
        from .reporter import export_json
        export_json(results, path)
