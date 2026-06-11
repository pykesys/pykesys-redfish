from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import RedfishClient


class RedfishResource:
    """Base class for all Redfish resource wrappers.

    Fetches and caches the resource JSON on first property access.
    Call refresh() to invalidate the cache.
    """

    def __init__(self, client: "RedfishClient", uri: str):
        self._client = client
        self._uri = uri
        self._data: dict[str, Any] | None = None

    @property
    def uri(self) -> str:
        return self._uri

    def _fetch(self) -> dict[str, Any]:
        if self._data is None:
            self._data = self._client.get(self._uri)
        return self._data

    def refresh(self) -> None:
        self._data = None

    def _get(self, *keys: str, default: Any = None) -> Any:
        data = self._fetch()
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key, default)
        return data
