from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_temperatures(node_id: int) -> list[dict]:
    return [
        {
            "Name": "Inlet Temp",
            "ReadingCelsius": round(21.0 + node_id * 0.3, 1),
            "UpperThresholdCritical": 55.0,
            "UpperThresholdNonCritical": 45.0,
            "Status": {"Health": "OK", "State": "Enabled"},
        },
        {
            "Name": "CPU1 Temp",
            "ReadingCelsius": 44.0,
            "UpperThresholdCritical": 85.0,
            "UpperThresholdNonCritical": 75.0,
            "Status": {"Health": "OK", "State": "Enabled"},
        },
        {
            "Name": "CPU2 Temp",
            "ReadingCelsius": 42.0,
            "UpperThresholdCritical": 85.0,
            "UpperThresholdNonCritical": 75.0,
            "Status": {"Health": "OK", "State": "Enabled"},
        },
    ]


def _default_fans() -> list[dict]:
    return [
        {"Name": "Fan 1A", "Reading": 3200, "ReadingUnits": "RPM", "Status": {"Health": "OK", "State": "Enabled"}},
        {"Name": "Fan 1B", "Reading": 3100, "ReadingUnits": "RPM", "Status": {"Health": "OK", "State": "Enabled"}},
        {"Name": "Fan 2A", "Reading": 3300, "ReadingUnits": "RPM", "Status": {"Health": "OK", "State": "Enabled"}},
        {"Name": "Fan 2B", "Reading": 3250, "ReadingUnits": "RPM", "Status": {"Health": "OK", "State": "Enabled"}},
    ]


def _default_power_supplies() -> list[dict]:
    return [
        {"Name": "PSU1", "PowerOutputWatts": 450.0, "LineInputVoltage": 220.0, "Status": {"Health": "OK", "State": "Enabled"}},
        {"Name": "PSU2", "PowerOutputWatts": 448.0, "LineInputVoltage": 220.0, "Status": {"Health": "OK", "State": "Enabled"}},
    ]


def _default_firmware() -> list[dict]:
    return [
        {"Id": "BIOS", "Name": "System BIOS", "Version": "1.0.0", "Updateable": True},
        {"Id": "BMC",  "Name": "BMC Firmware", "Version": "4.0.0", "Updateable": True},
        {"Id": "NIC1", "Name": "Network Adapter 1", "Version": "22.0.7", "Updateable": False},
        {"Id": "HBA1", "Name": "Storage HBA", "Version": "3.1.2", "Updateable": False},
    ]


def _default_accounts() -> list[dict]:
    # Admin account is separate (stored in admin_user/admin_pass); this list holds non-admin accounts.
    return []


class NodeState:
    """In-memory state machine representing a single emulated BMC."""

    def __init__(self, node_id: int, admin_user: str = "admin", admin_pass: str = "redfish"):
        self.node_id = node_id
        self.admin_user = admin_user
        self.admin_pass = admin_pass

        # Identity (static)
        self.hostname = f"sim-node-{node_id:02d}.bmc.local"
        self.model = f"SimServer G{(node_id - 1) // 3 + 1}00"
        self.serial_number = f"SIM{node_id:04d}"
        self.bios_version = "1.0.0"
        self.bmc_firmware_version = "4.0.0"
        self.manufacturer = "PyKeSys Sim"
        self.memory_gib = 128 + ((node_id - 1) % 4) * 64  # 128 / 192 / 256 / 320
        self.processor_count = 2
        self.processor_model = "Sim Xeon 6438M"

        # Mutable hardware state
        self.power_state = "On"
        self.health = "OK"
        self.indicator_led = "Off"
        self.boot_override_target = "None"
        self.boot_override_enabled = "Disabled"
        self.boot_override_mode = "UEFI"

        # Sensor data
        self.temperatures: list[dict] = _default_temperatures(node_id)
        self.fans: list[dict] = _default_fans()
        self.power_supplies: list[dict] = _default_power_supplies()

        # Inventory
        self.firmware: list[dict] = _default_firmware()
        self.accounts: list[dict] = _default_accounts()
        self._account_counter = 2  # admin is implicitly id=1

        # SEL log
        self.sel_log: list[dict] = []
        self._sel_counter = 1

        # Active sessions: token → session_id
        self.sessions: dict[str, str] = {}
        self._session_counter = 0

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, username: str, password: str) -> tuple[str, str] | None:
        """Validate credentials and return (token, session_id) or None."""
        valid = (username == self.admin_user and password == self.admin_pass)
        if not valid:
            for acc in self.accounts:
                if acc["UserName"] == username and acc.get("Password") == password and acc["Enabled"]:
                    valid = True
                    break
        if not valid:
            return None
        self._session_counter += 1
        token = uuid.uuid4().hex
        session_id = str(self._session_counter)
        self.sessions[token] = session_id
        return token, session_id

    def validate_token(self, token: str) -> bool:
        return token in self.sessions

    def validate_basic(self, username: str, password: str) -> bool:
        if username == self.admin_user and password == self.admin_pass:
            return True
        for acc in self.accounts:
            if acc["UserName"] == username and acc.get("Password") == password and acc["Enabled"]:
                return True
        return False

    def delete_session_by_id(self, session_id: str) -> None:
        self.sessions = {t: s for t, s in self.sessions.items() if s != session_id}

    def delete_session_by_token(self, token: str) -> None:
        self.sessions.pop(token, None)

    # ------------------------------------------------------------------
    # Power state machine
    # ------------------------------------------------------------------

    RESET_TYPE_MAP: dict[str, dict[str, str]] = {
        "On":               {"On": "On",  "Off": "On"},
        "ForceOn":          {"On": "On",  "Off": "On"},
        "ForceOff":         {"On": "Off", "Off": "Off"},
        "GracefulShutdown": {"On": "Off", "Off": "Off"},
        "GracefulRestart":  {"On": "On",  "Off": "On"},
        "ForceRestart":     {"On": "On",  "Off": "On"},
        "PushPowerButton":  {"On": "Off", "Off": "On"},
        "Nmi":              {"On": "On",  "Off": "Off"},
    }

    def apply_reset(self, reset_type: str) -> bool:
        mapping = self.RESET_TYPE_MAP.get(reset_type)
        if mapping is None:
            return False
        self.power_state = mapping.get(self.power_state, self.power_state)
        return True

    # ------------------------------------------------------------------
    # SEL log
    # ------------------------------------------------------------------

    def add_sel_entry(self, severity: str, message: str, message_id: str = "") -> dict:
        entry = {
            "Id": str(self._sel_counter),
            "Created": _now(),
            "Severity": severity,
            "Message": message,
            "MessageId": message_id or f"General.1.0.{severity}",
            "EntryType": "Event",
        }
        self._sel_counter += 1
        self.sel_log.append(entry)
        return entry

    def clear_sel(self) -> None:
        self.sel_log = []
        self._sel_counter = 1

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def get_account(self, account_id: str) -> dict | None:
        for acc in self.accounts:
            if acc["Id"] == account_id:
                return acc
        return None

    def add_account(self, username: str, password: str, role: str = "Operator") -> dict:
        acc = {
            "Id": str(self._account_counter),
            "UserName": username,
            "Password": password,
            "RoleId": role,
            "Enabled": True,
        }
        self._account_counter += 1
        self.accounts.append(acc)
        return acc

    def delete_account(self, account_id: str) -> bool:
        original = len(self.accounts)
        self.accounts = [a for a in self.accounts if a["Id"] != account_id]
        return len(self.accounts) < original

    # ------------------------------------------------------------------
    # Scenario / reset
    # ------------------------------------------------------------------

    def reset_to_healthy(self) -> None:
        self.power_state = "On"
        self.health = "OK"
        self.indicator_led = "Off"
        self.boot_override_target = "None"
        self.boot_override_enabled = "Disabled"
        self.temperatures = _default_temperatures(self.node_id)
        self.fans = _default_fans()
        self.power_supplies = _default_power_supplies()
        self.firmware = _default_firmware()
        self.sel_log = []
        self._sel_counter = 1

    def apply_scenario(self, overrides: dict[str, Any]) -> None:
        """Apply a dict of field overrides from a scenario file."""
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)
