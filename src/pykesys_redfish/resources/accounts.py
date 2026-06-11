from __future__ import annotations

from .base import RedfishResource


class AccountService(RedfishResource):
    """Wraps the Redfish AccountService resource.

    Provides account and role management operations.
    """

    @property
    def min_password_length(self) -> int | None:
        return self._get("MinPasswordLength")

    @property
    def lockout_threshold(self) -> int | None:
        return self._get("AccountLockoutThreshold")

    @property
    def lockout_duration(self) -> int | None:
        return self._get("AccountLockoutDuration")

    def _accounts_uri(self) -> str:
        return self._get("Accounts", "@odata.id") or self._uri.rstrip("/") + "/Accounts/"

    def accounts(self) -> list[dict]:
        data = self._client.get(self._accounts_uri())
        return [self._client.get(m["@odata.id"]) for m in data.get("Members", [])]

    def create_account(self, username: str, password: str, role: str = "Operator") -> dict:
        result = self._client.post(
            self._accounts_uri(),
            {"UserName": username, "Password": password, "RoleId": role, "Enabled": True},
        )
        return result or {}

    def delete_account(self, account_uri: str) -> None:
        self._client.delete(account_uri)

    def set_password(self, account_uri: str, new_password: str) -> None:
        self._client.patch(account_uri, {"Password": new_password})

    def set_enabled(self, account_uri: str, enabled: bool) -> None:
        self._client.patch(account_uri, {"Enabled": enabled})

    def set_lockout_policy(
        self,
        threshold: int,
        duration: int,
        reset_after: int | None = None,
    ) -> None:
        body: dict = {
            "AccountLockoutThreshold": threshold,
            "AccountLockoutDuration": duration,
        }
        if reset_after is not None:
            body["AccountLockoutCounterResetAfter"] = reset_after
        self._client.patch(self._uri, body)
        self.refresh()
