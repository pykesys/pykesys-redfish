from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .exceptions import (
    RedfishAuthError,
    RedfishConflictError,
    RedfishError,
    RedfishNotFoundError,
    RedfishServerError,
    RedfishTimeoutError,
)


class RedfishSession:
    """Manages a Redfish session token lifecycle.

    Creates a session on connect(), stores the X-Auth-Token, and
    deletes the session on close(). Falls back to HTTP Basic Auth
    when auth="basic" is requested.

    Supports path-prefixed base URLs (e.g. http://emulator:8888/bmc/1)
    for multi-node emulator environments. The path portion is extracted
    and prepended to every request URI automatically.
    """

    SESSION_URI = "/redfish/v1/SessionService/Sessions/"

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        auth: str = "session",
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.auth_mode = auth

        # Extract optional path prefix (e.g. "/bmc/1") from base_url so that
        # absolute Redfish paths like /redfish/v1/ are correctly routed on
        # emulators that serve multiple nodes under different path prefixes.
        _parsed = urlparse(self.base_url)
        self._path_prefix: str = _parsed.path.rstrip("/")  # "" for plain hosts
        self._http_root: str = f"{_parsed.scheme}://{_parsed.netloc}"

        self._token: str | None = None
        self._session_uri: str | None = None
        self._http: httpx.Client | None = None

    def connect(self) -> None:
        self._http = httpx.Client(
            base_url=self._http_root,
            verify=self.verify_ssl,
            timeout=self.timeout,
        )
        if self.auth_mode == "session":
            self._create_session()

    def _p(self, uri: str) -> str:
        """Prepend path prefix to a Redfish URI."""
        return self._path_prefix + uri

    def _create_session(self) -> None:
        resp = self._raw_post(
            self.SESSION_URI,
            json={"UserName": self.username, "Password": self.password},
        )
        self._token = resp.headers.get("X-Auth-Token")
        self._session_uri = resp.headers.get("Location") or resp.json().get(
            "@odata.id"
        )

    def close(self) -> None:
        if self._token and self._session_uri:
            try:
                uri = self._session_uri
                # Strip absolute base_url prefix if Location header was absolute
                if uri.startswith(self.base_url):
                    uri = uri[len(self.base_url):]
                self._http.delete(
                    self._p(uri),
                    headers={"X-Auth-Token": self._token},
                )
            except Exception:
                pass
        if self._http:
            self._http.close()
        self._token = None
        self._session_uri = None

    def _auth_headers(self) -> dict[str, str]:
        if self.auth_mode == "session" and self._token:
            return {"X-Auth-Token": self._token}
        return {}

    def _auth_kwargs(self) -> dict:
        if self.auth_mode == "basic":
            return {"auth": (self.username, self.password)}
        return {}

    def _raw_post(self, uri: str, **kwargs) -> httpx.Response:
        try:
            resp = self._http.post(self._p(uri), **kwargs)
        except httpx.TimeoutException as exc:
            raise RedfishTimeoutError(str(exc)) from exc
        _raise_for_status(resp)
        return resp

    def get(self, uri: str) -> dict:
        try:
            resp = self._http.get(
                self._p(uri),
                headers=self._auth_headers(),
                **self._auth_kwargs(),
            )
        except httpx.TimeoutException as exc:
            raise RedfishTimeoutError(str(exc)) from exc
        _raise_for_status(resp)
        return resp.json()

    def post(self, uri: str, body: dict | None = None) -> dict | None:
        try:
            resp = self._http.post(
                self._p(uri),
                json=body or {},
                headers={"Content-Type": "application/json", **self._auth_headers()},
                **self._auth_kwargs(),
            )
        except httpx.TimeoutException as exc:
            raise RedfishTimeoutError(str(exc)) from exc
        _raise_for_status(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def patch(self, uri: str, body: dict) -> dict | None:
        try:
            resp = self._http.patch(
                self._p(uri),
                json=body,
                headers={"Content-Type": "application/json", **self._auth_headers()},
                **self._auth_kwargs(),
            )
        except httpx.TimeoutException as exc:
            raise RedfishTimeoutError(str(exc)) from exc
        _raise_for_status(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def delete(self, uri: str) -> None:
        try:
            resp = self._http.delete(
                self._p(uri),
                headers=self._auth_headers(),
                **self._auth_kwargs(),
            )
        except httpx.TimeoutException as exc:
            raise RedfishTimeoutError(str(exc)) from exc
        _raise_for_status(resp)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    url = str(resp.url)
    code = resp.status_code
    try:
        msg = resp.json().get("error", {}).get("message", resp.text)
    except Exception:
        msg = resp.text

    if code in (401, 403):
        raise RedfishAuthError(msg, status_code=code, url=url)
    if code == 404:
        raise RedfishNotFoundError(msg, status_code=code, url=url)
    if code == 409:
        raise RedfishConflictError(msg, status_code=code, url=url)
    if code in (500, 503):
        raise RedfishServerError(msg, status_code=code, url=url)
    raise RedfishError(msg, status_code=code, url=url)
