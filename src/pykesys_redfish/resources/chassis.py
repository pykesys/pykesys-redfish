from __future__ import annotations

from .base import RedfishResource


class Chassis(RedfishResource):
    """Wraps a Redfish Chassis resource.

    Provides typed access to physical enclosure data: temperatures,
    fans, power supplies, and identification LED.
    """

    @property
    def id(self) -> str | None:
        return self._get("Id")

    @property
    def chassis_type(self) -> str | None:
        return self._get("ChassisType")

    @property
    def manufacturer(self) -> str | None:
        return self._get("Manufacturer")

    @property
    def model(self) -> str | None:
        return self._get("Model")

    @property
    def serial_number(self) -> str | None:
        return self._get("SerialNumber")

    @property
    def health(self) -> str | None:
        return self._get("Status", "Health")

    @property
    def indicator_led(self) -> str | None:
        return self._get("IndicatorLED")

    # ------------------------------------------------------------------
    # Thermal
    # ------------------------------------------------------------------

    def temperatures(self) -> list[dict]:
        uri = self._uri.rstrip("/") + "/Thermal/"
        data = self._client.get(uri)
        return data.get("Temperatures", [])

    def fans(self) -> list[dict]:
        uri = self._uri.rstrip("/") + "/Thermal/"
        data = self._client.get(uri)
        return data.get("Fans", [])

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    def power_supplies(self) -> list[dict]:
        uri = self._uri.rstrip("/") + "/Power/"
        data = self._client.get(uri)
        return data.get("PowerSupplies", [])

    def power_consumed_watts(self) -> float | None:
        uri = self._uri.rstrip("/") + "/Power/"
        data = self._client.get(uri)
        controls = data.get("PowerControl", [])
        if controls:
            return controls[0].get("PowerConsumedWatts")
        return None

    # ------------------------------------------------------------------
    # LED
    # ------------------------------------------------------------------

    def identify(self, state: str = "Blinking") -> None:
        self._client.patch(self._uri, {"IndicatorLED": state})
        self.refresh()

    def identify_off(self) -> None:
        self.identify("Off")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "id": self.id,
            "chassis_type": self.chassis_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "serial_number": self.serial_number,
            "health": self.health,
        }
