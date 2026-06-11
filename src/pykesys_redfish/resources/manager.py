from __future__ import annotations

from .base import RedfishResource

RESET_ACTION = "#Manager.Reset"
RESET_DEFAULTS_ACTION = "#Manager.ResetToDefaults"


class Manager(RedfishResource):
    """Wraps a Redfish Manager resource (the BMC itself).

    Provides access to BMC firmware version, network configuration,
    protocol settings, and BMC reset actions.
    """

    @property
    def id(self) -> str | None:
        return self._get("Id")

    @property
    def firmware_version(self) -> str | None:
        return self._get("FirmwareVersion")

    @property
    def manager_type(self) -> str | None:
        return self._get("ManagerType")

    @property
    def health(self) -> str | None:
        return self._get("Status", "Health")

    @property
    def model(self) -> str | None:
        return self._get("Model")

    # ------------------------------------------------------------------
    # Network protocols
    # ------------------------------------------------------------------

    def network_protocols(self) -> dict:
        uri = self._get("NetworkProtocol", "@odata.id") or self._uri.rstrip("/") + "/NetworkProtocol/"
        return self._client.get(uri)

    def set_protocol_enabled(self, protocol: str, enabled: bool) -> None:
        uri = self._get("NetworkProtocol", "@odata.id") or self._uri.rstrip("/") + "/NetworkProtocol/"
        self._client.patch(uri, {protocol: {"ProtocolEnabled": enabled}})

    def set_ntp_servers(self, servers: list[str]) -> None:
        uri = self._get("NetworkProtocol", "@odata.id") or self._uri.rstrip("/") + "/NetworkProtocol/"
        self._client.patch(uri, {"NTP": {"ProtocolEnabled": True, "NTPServers": servers}})

    # ------------------------------------------------------------------
    # Network interfaces
    # ------------------------------------------------------------------

    def ethernet_interfaces(self) -> list[dict]:
        uri = self._uri.rstrip("/") + "/EthernetInterfaces/"
        data = self._client.get(uri)
        return [self._client.get(m["@odata.id"]) for m in data.get("Members", [])]

    # ------------------------------------------------------------------
    # BMC actions
    # ------------------------------------------------------------------

    def _action_uri(self, action_key: str, fallback_suffix: str) -> str:
        actions = self._get("Actions") or {}
        target = actions.get(action_key, {}).get("target")
        return target or self._uri.rstrip("/") + fallback_suffix

    def reset(self, reset_type: str = "GracefulRestart") -> None:
        uri = self._action_uri(RESET_ACTION, "/Actions/Manager.Reset")
        self._client.post(uri, {"ResetType": reset_type})

    def reset_to_defaults(self, reset_type: str = "ResetAll") -> None:
        uri = self._action_uri(RESET_DEFAULTS_ACTION, "/Actions/Manager.ResetToDefaults")
        self._client.post(uri, {"ResetToDefaultsType": reset_type})

    # ------------------------------------------------------------------
    # BMC log
    # ------------------------------------------------------------------

    def log_entries(self, log_service: str = "Log1") -> list[dict]:
        base = self._uri.rstrip("/")
        data = self._client.get(f"{base}/LogServices/{log_service}/Entries/")
        return data.get("Members", [])

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "id": self.id,
            "manager_type": self.manager_type,
            "firmware_version": self.firmware_version,
            "model": self.model,
            "health": self.health,
        }
