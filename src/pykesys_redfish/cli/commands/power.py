from __future__ import annotations

import typer

from ..output import console, power_color

app = typer.Typer(help="Power management commands.")

_OPTS = dict(
    host=typer.Option(None, "--host", "-H"),
    user=typer.Option(None, "--user", "-u"),
    password=typer.Option(None, "--pass", "-p"),
    no_verify=typer.Option(False, "--no-verify"),
)


def _client(host, user, password, no_verify):
    from ..main import make_client
    return make_client(host, user, password, no_verify)


@app.command("status")
def power_status(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Show current power state."""
    with _client(host, user, password, no_verify) as rf:
        state = rf.system().power_state
        console.print(f"Power state: [{power_color(state)}]{state}[/]")


@app.command("on")
def power_on(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Power on the system."""
    with _client(host, user, password, no_verify) as rf:
        rf.system().power_on()
        console.print("[green]Power-on command sent.[/]")


@app.command("off")
def power_off(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    force: bool = typer.Option(False, "--force", "-f", help="Force immediate power off"),
) -> None:
    """Power off the system (graceful by default)."""
    with _client(host, user, password, no_verify) as rf:
        s = rf.system()
        if force:
            s.power_off()
            console.print("[yellow]Force power-off sent.[/]")
        else:
            s.graceful_shutdown()
            console.print("[yellow]Graceful shutdown sent.[/]")


@app.command("reset")
def power_reset(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    reset_type: str = typer.Option("GracefulRestart", "--type", "-t", help="ResetType value"),
) -> None:
    """Reset the system. Use --type to specify the ResetType."""
    with _client(host, user, password, no_verify) as rf:
        rf.system().reset(reset_type)
        console.print(f"[yellow]Reset ({reset_type}) sent.[/]")


@app.command("nmi")
def power_nmi(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Inject a Non-Maskable Interrupt (triggers crash dump)."""
    with _client(host, user, password, no_verify) as rf:
        rf.system().nmi()
        console.print("[red]NMI injected.[/]")
