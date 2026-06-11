class RedfishError(Exception):
    """Base exception for all pykesys-redfish errors."""

    def __init__(self, message: str, status_code: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RedfishAuthError(RedfishError):
    """Authentication failed (401) or insufficient privilege (403)."""


class RedfishNotFoundError(RedfishError):
    """Requested resource URI does not exist (404)."""


class RedfishConflictError(RedfishError):
    """State conflict — e.g. power-on when already powered on (409)."""


class RedfishServerError(RedfishError):
    """BMC-side error (500/503)."""


class RedfishTimeoutError(RedfishError):
    """Request timed out."""
