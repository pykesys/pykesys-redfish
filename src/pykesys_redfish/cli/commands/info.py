from __future__ import annotations

import os

import typer

from ...client import RedfishClient
from ..output import console, system_table


def info(
    host: str = typer.Option(None, "--host", "-H", help="BMC hostname or IP"),
    user: str = typer.Option(None, "--user", "-u", help="Username"),
    password: str = typer.Option(None, "--pass", "-p", help="Password"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip TLS verification"),
) -> None:
    """Show a summary of the system managed by this BMC."""
    from ..main import make_client

    with make_client(host, user, password, no_verify) as rf:
        system = rf.system()
        console.print(system_table(system.summary()))
