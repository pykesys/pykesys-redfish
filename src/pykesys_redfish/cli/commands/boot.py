from __future__ import annotations

import typer

from ..output import console

app = typer.Typer(help="Boot source override commands.")


def _client(host, user, password, no_verify):
    from ..main import make_client
    return make_client(host, user, password, no_verify)


@app.command("once")
def boot_once(
    target: str = typer.Argument(help="Boot target: Pxe, Usb, Hdd, Cd, BiosSetup, UefiShell, etc."),
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    mode: str = typer.Option(None, "--mode", "-m", help="UEFI or Legacy"),
) -> None:
    """Set a one-time boot override for the next boot."""
    with _client(host, user, password, no_verify) as rf:
        rf.system().set_boot_once(target, mode=mode)
        console.print(f"[green]Boot override set: {target} (Once)[/]")


@app.command("clear")
def boot_clear(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Clear the boot override — revert to normal boot order."""
    with _client(host, user, password, no_verify) as rf:
        rf.system().clear_boot_override()
        console.print("[green]Boot override cleared.[/]")


@app.command("status")
def boot_status(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Show current boot override settings."""
    with _client(host, user, password, no_verify) as rf:
        s = rf.system()
        console.print(f"Target:  {s.boot_source_override_target}")
        console.print(f"Enabled: {s.boot_source_override_enabled}")
        console.print(f"Allowed: {', '.join(s.boot_allowable_values)}")
