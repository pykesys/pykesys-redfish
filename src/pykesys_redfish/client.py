from __future__ import annotations

import os
from types import TracebackType
from typing import TYPE_CHECKING

from .exceptions import RedfishNotFoundError
from .session import RedfishSession

if TYPE_CHECKING:
    from .resources.accounts import AccountService
    from .resources.chassis import Chassis
    from .resources.manager import Manager
    from .resources.system import ComputerSystem


class RedfishClient:
    """Entry point for all Redfish operations against a single BMC.

    Usage::

        with RedfishClient("https://bmc-host", "admin", "password") as rf:
            system = rf.system()
            print(system.power_state)
            system.power_on()

    Credentials may also come from environment variables RF_HOST, RF_USER,
    RF_PASS when constructing via RedfishClient.from_env().
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        auth: str = "session",
    ):
        self._session = RedfishSession(
            base_url=base_url,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            timeout=timeout,
            auth=auth,
        )
        self._connected = False

    @classmethod
    def from_env(cls) -> "RedfishClient":
        verify = os.environ.get("RF_VERIFY_SSL", "true").lower() != "false"
        return cls(
            base_url=os.environ["RF_HOST"],
            username=os.environ["RF_USER"],
            password=os.environ["RF_PASS"],
            verify_ssl=verify,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "RedfishClient":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        if not self._connected:
            self._session.connect()
            self._connected = True

    def close(self) -> None:
        # Always close the underlying session: if connect() raised mid-way
        # (e.g. auth failure during session creation), _connected stays False
        # but the httpx.Client was already opened and must be released.
        self._session.close()
        self._connected = False

    # ------------------------------------------------------------------
    # Low-level HTTP pass-through (used by resource objects)
    # ------------------------------------------------------------------

    def get(self, uri: str) -> dict:
        return self._session.get(uri)

    def post(self, uri: str, body: dict | None = None) -> dict | None:
        return self._session.post(uri, body)

    def patch(self, uri: str, body: dict) -> dict | None:
        return self._session.patch(uri, body)

    def delete(self, uri: str) -> None:
        return self._session.delete(uri)

    # ------------------------------------------------------------------
    # Resource accessors
    # ------------------------------------------------------------------

    def _member_uri(self, collection_uri: str, index: int) -> str:
        data = self.get(collection_uri)
        members = data.get("Members", [])
        if not members:
            raise RedfishNotFoundError(
                f"No members in collection {collection_uri}",
                url=collection_uri,
            )
        if index >= len(members) or index < -len(members):
            raise RedfishNotFoundError(
                f"Index {index} out of range for collection {collection_uri} "
                f"({len(members)} members)",
                url=collection_uri,
            )
        return members[index]["@odata.id"]

    def system(self, index: int = 0) -> "ComputerSystem":
        from .resources.system import ComputerSystem

        return ComputerSystem(self, self._member_uri("/redfish/v1/Systems/", index))

    def chassis(self, index: int = 0) -> "Chassis":
        from .resources.chassis import Chassis

        return Chassis(self, self._member_uri("/redfish/v1/Chassis/", index))

    def manager(self, index: int = 0) -> "Manager":
        from .resources.manager import Manager

        return Manager(self, self._member_uri("/redfish/v1/Managers/", index))

    def account_service(self) -> "AccountService":
        from .resources.accounts import AccountService

        root = self.get("/redfish/v1/")
        uri = root["AccountService"]["@odata.id"]
        return AccountService(self, uri)
