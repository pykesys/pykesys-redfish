from __future__ import annotations

import os
from typing import Annotated

import typer

from ..client import RedfishClient

app = typer.Typer(
    name="rf",
    help="Redfish BMC management CLI. Credentials can be set via RF_HOST / RF_USER / RF_PASS.",
    no_args_is_help=True,
)

_HOST_HELP = "BMC hostname or IP (overrides RF_HOST)"
_USER_HELP = "Username (overrides RF_USER)"
_PASS_HELP = "Password (overrides RF_PASS)"
_NOVERIFY_HELP = "Disable TLS certificate verification"


def make_client(host: str | None, user: str | None, password: str | None, no_verify: bool) -> RedfishClient:
    h = host or os.environ.get("RF_HOST") or typer.prompt("BMC host")
    u = user or os.environ.get("RF_USER") or typer.prompt("Username")
    p = password or os.environ.get("RF_PASS") or typer.prompt("Password", hide_input=True)
    return RedfishClient(h, u, p, verify_ssl=not no_verify)


# ------------------------------------------------------------------
# Import sub-command modules (registers them on app)
# ------------------------------------------------------------------

from .commands import power, boot, logs, firmware, accounts  # noqa: E402, F401
from .commands.info import info as _info_cmd  # noqa: E402

app.add_typer(power.app, name="power")
app.add_typer(boot.app, name="boot")
app.add_typer(logs.app, name="logs")
app.add_typer(firmware.app, name="firmware")
app.add_typer(accounts.app, name="accounts")
app.command("info")(_info_cmd)
