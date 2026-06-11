from __future__ import annotations

from typing import TYPE_CHECKING

from .base import RedfishResource

if TYPE_CHECKING:
    from ..client import RedfishClient

RESET_ACTION = "#ComputerSystem.Reset"


class ComputerSystem(RedfishResource):
    """Wraps a Redfish ComputerSystem resource.

    Provides typed properties and action methods for power management,
    boot override, hardware inventory, and identification LED.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def id(self) -> str | None:
        return self._get("Id")

    @property
    def hostname(self) -> str | None:
        return self._get("HostName")

    @property
    def serial_number(self) -> str | None:
        return self._get("SerialNumber")

    @property
    def model(self) -> str | None:
        return self._get("Model")

    @property
    def sku(self) -> str | None:
        return self._get("SKU")

    @property
    def manufacturer(self) -> str | None:
        return self._get("Manufacturer")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def power_state(self) -> str | None:
        return self._get("PowerState")

    @property
    def health(self) -> str | None:
        return self._get("Status", "Health")

    @property
    def state(self) -> str | None:
        return self._get("Status", "State")

    @property
    def bios_version(self) -> str | None:
        return self._get("BiosVersion")

    # ------------------------------------------------------------------
    # Hardware summary
    # ------------------------------------------------------------------

    @property
    def total_memory_gib(self) -> float | None:
        return self._get("MemorySummary", "TotalSystemMemoryGiB")

    @property
    def processor_count(self) -> int | None:
        return self._get("ProcessorSummary", "Count")

    @property
    def processor_model(self) -> str | None:
        return self._get("ProcessorSummary", "Model")

    # ------------------------------------------------------------------
    # Boot
    # ------------------------------------------------------------------

    @property
    def boot_source_override_target(self) -> str | None:
        return self._get("Boot", "BootSourceOverrideTarget")

    @property
    def boot_source_override_enabled(self) -> str | None:
        return self._get("Boot", "BootSourceOverrideEnabled")

    @property
    def boot_allowable_values(self) -> list[str]:
        return self._get("Boot", "BootSourceOverrideTarget@Redfish.AllowableValues") or []

    # ------------------------------------------------------------------
    # LED
    # ------------------------------------------------------------------

    @property
    def indicator_led(self) -> str | None:
        return self._get("IndicatorLED")

    # ------------------------------------------------------------------
    # Power actions
    # ------------------------------------------------------------------

    def _reset_action_uri(self) -> str:
        actions = self._get("Actions") or {}
        target = actions.get(RESET_ACTION, {}).get("target")
        if target:
            return target
        return self._uri.rstrip("/") + "/Actions/ComputerSystem.Reset"

    def reset(self, reset_type: str) -> None:
        self._client.post(self._reset_action_uri(), {"ResetType": reset_type})
        self.refresh()

    def power_on(self) -> None:
        self.reset("On")

    def power_off(self) -> None:
        self.reset("ForceOff")

    def graceful_shutdown(self) -> None:
        self.reset("GracefulShutdown")

    def graceful_restart(self) -> None:
        self.reset("GracefulRestart")

    def force_restart(self) -> None:
        self.reset("ForceRestart")

    def nmi(self) -> None:
        self.reset("Nmi")

    # ------------------------------------------------------------------
    # Boot override
    # ------------------------------------------------------------------

    def set_boot_once(self, target: str, mode: str | None = None) -> None:
        body: dict = {"Boot": {"BootSourceOverrideTarget": target, "BootSourceOverrideEnabled": "Once"}}
        if mode:
            body["Boot"]["BootSourceOverrideMode"] = mode
        self._client.patch(self._uri, body)
        self.refresh()

    def clear_boot_override(self) -> None:
        self._client.patch(
            self._uri,
            {"Boot": {"BootSourceOverrideTarget": "None", "BootSourceOverrideEnabled": "Disabled"}},
        )
        self.refresh()

    # ------------------------------------------------------------------
    # Identification LED
    # ------------------------------------------------------------------

    def identify(self, state: str = "Blinking") -> None:
        self._client.patch(self._uri, {"IndicatorLED": state})
        self.refresh()

    def identify_off(self) -> None:
        self.identify("Off")

    # ------------------------------------------------------------------
    # Sub-collections
    # ------------------------------------------------------------------

    def processors(self) -> list[dict]:
        uri = self._get("Processors", "@odata.id") or self._uri + "/Processors/"
        data = self._client.get(uri)
        return [self._client.get(m["@odata.id"]) for m in data.get("Members", [])]

    def memory(self) -> list[dict]:
        uri = self._get("Memory", "@odata.id") or self._uri + "/Memory/"
        data = self._client.get(uri)
        return [self._client.get(m["@odata.id"]) for m in data.get("Members", [])]

    def storage(self) -> list[dict]:
        from .storage import Storage

        uri = self._get("Storage", "@odata.id") or self._uri + "/Storage/"
        data = self._client.get(uri)
        return [Storage(self._client, m["@odata.id"]) for m in data.get("Members", [])]

    def log_entries(self, log_service: str = "Sel") -> list[dict]:
        base = self._uri.rstrip("/")
        entries_uri = f"{base}/LogServices/{log_service}/Entries/"
        data = self._client.get(entries_uri)
        return data.get("Members", [])

    def clear_log(self, log_service: str = "Sel") -> None:
        base = self._uri.rstrip("/")
        action_uri = f"{base}/LogServices/{log_service}/Actions/LogService.ClearLog"
        self._client.post(action_uri, {})

    # ------------------------------------------------------------------
    # Summary dict (used by CLI and fleet)
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "serial_number": self.serial_number,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "bios_version": self.bios_version,
            "power_state": self.power_state,
            "health": self.health,
            "total_memory_gib": self.total_memory_gib,
            "processor_count": self.processor_count,
            "processor_model": self.processor_model,
        }
