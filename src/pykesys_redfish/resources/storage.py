from __future__ import annotations

from .base import RedfishResource


class Storage(RedfishResource):
    """Wraps a Redfish Storage controller resource."""

    @property
    def id(self) -> str | None:
        return self._get("Id")

    @property
    def name(self) -> str | None:
        return self._get("Name")

    @property
    def health(self) -> str | None:
        return self._get("Status", "Health")

    def drives(self) -> list["Drive"]:
        drive_links = self._get("Drives") or []
        return [Drive(self._client, d["@odata.id"]) for d in drive_links]

    def volumes(self) -> list[dict]:
        uri = self._get("Volumes", "@odata.id") or self._uri.rstrip("/") + "/Volumes/"
        data = self._client.get(uri)
        return [self._client.get(m["@odata.id"]) for m in data.get("Members", [])]

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "health": self.health,
            "drive_count": len(self._get("Drives") or []),
        }


class Drive(RedfishResource):
    """Wraps a Redfish Drive resource."""

    @property
    def id(self) -> str | None:
        return self._get("Id")

    @property
    def name(self) -> str | None:
        return self._get("Name")

    @property
    def health(self) -> str | None:
        return self._get("Status", "Health")

    @property
    def capacity_bytes(self) -> int | None:
        return self._get("CapacityBytes")

    @property
    def capacity_gib(self) -> float | None:
        cb = self.capacity_bytes
        return round(cb / (1024**3), 1) if cb is not None else None

    @property
    def protocol(self) -> str | None:
        return self._get("Protocol")

    @property
    def media_type(self) -> str | None:
        return self._get("MediaType")

    @property
    def model(self) -> str | None:
        return self._get("Model")

    @property
    def serial_number(self) -> str | None:
        return self._get("SerialNumber")

    @property
    def predicted_life_left_pct(self) -> int | None:
        return self._get("PredictedMediaLifeLeftPercent")

    def summary(self) -> dict:
        return {
            "id": self.id,
            "model": self.model,
            "serial_number": self.serial_number,
            "capacity_gib": self.capacity_gib,
            "protocol": self.protocol,
            "media_type": self.media_type,
            "health": self.health,
            "predicted_life_left_pct": self.predicted_life_left_pct,
        }
