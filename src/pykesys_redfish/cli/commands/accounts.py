from __future__ import annotations

import typer

from ..output import console, accounts_table

app = typer.Typer(help="User account management commands.")


def _client(host, user, password, no_verify):
    from ..main import make_client
    return make_client(host, user, password, no_verify)


@app.command("list")
def accounts_list(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """List user accounts."""
    with _client(host, user, password, no_verify) as rf:
        accts = rf.account_service().accounts()
        console.print(accounts_table(accts))


@app.command("create")
def accounts_create(
    new_user: str = typer.Argument(help="New username"),
    role: str = typer.Option("Operator", "--role", "-r", help="Administrator, Operator, ReadOnly"),
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Create a new user account (prompts for password)."""
    new_pass = typer.prompt(f"Password for {new_user}", hide_input=True, confirmation_prompt=True)
    with _client(host, user, password, no_verify) as rf:
        rf.account_service().create_account(new_user, new_pass, role)
        console.print(f"[green]Account '{new_user}' created with role '{role}'.[/]")


@app.command("delete")
def accounts_delete(
    account_uri: str = typer.Argument(help="Full Redfish URI of the account to delete"),
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete a user account by its Redfish URI."""
    if not yes:
        typer.confirm(f"Delete account at {account_uri}?", abort=True)
    with _client(host, user, password, no_verify) as rf:
        rf.account_service().delete_account(account_uri)
        console.print("[yellow]Account deleted.[/]")
