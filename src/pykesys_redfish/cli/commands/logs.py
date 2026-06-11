from __future__ import annotations

import typer

from ..output import console, log_table

app = typer.Typer(help="System event log commands.")


def _client(host, user, password, no_verify):
    from ..main import make_client
    return make_client(host, user, password, no_verify)


@app.command("list")
def logs_list(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    log_service: str = typer.Option("Sel", "--service", "-s", help="Log service name"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max entries to display"),
) -> None:
    """List system event log entries."""
    with _client(host, user, password, no_verify) as rf:
        entries = rf.system().log_entries(log_service)
        console.print(log_table(entries[-limit:]))
        console.print(f"[dim]{len(entries)} total entries[/]")


@app.command("clear")
def logs_clear(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    log_service: str = typer.Option("Sel", "--service", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Clear the system event log."""
    if not yes:
        typer.confirm("Clear the event log? This cannot be undone.", abort=True)
    with _client(host, user, password, no_verify) as rf:
        rf.system().clear_log(log_service)
        console.print("[yellow]Log cleared.[/]")
