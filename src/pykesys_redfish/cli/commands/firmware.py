from __future__ import annotations

import typer

from ..output import console, firmware_table

app = typer.Typer(help="Firmware inventory and update commands.")


def _client(host, user, password, no_verify):
    from ..main import make_client
    return make_client(host, user, password, no_verify)


@app.command("list")
def firmware_list(
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """List installed firmware components."""
    with _client(host, user, password, no_verify) as rf:
        data = rf.get("/redfish/v1/UpdateService/FirmwareInventory/")
        members = [rf.get(m["@odata.id"]) for m in data.get("Members", [])]
        console.print(firmware_table(members))


@app.command("update")
def firmware_update(
    image_uri: str = typer.Argument(help="HTTPS URI of the firmware image"),
    target: str = typer.Option(None, "--target", "-t", help="FirmwareInventory URI to target"),
    host: str = typer.Option(None, "--host", "-H"),
    user: str = typer.Option(None, "--user", "-u"),
    password: str = typer.Option(None, "--pass", "-p"),
    no_verify: bool = typer.Option(False, "--no-verify"),
) -> None:
    """Trigger a SimpleUpdate from a remote HTTPS firmware image."""
    body: dict = {"TransferProtocol": "HTTPS", "ImageURI": image_uri}
    if target:
        body["Targets"] = [target]
    with _client(host, user, password, no_verify) as rf:
        result = rf.post(
            "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            body,
        )
        if result:
            task_id = result.get("@odata.id", "")
            console.print(f"[green]Update started. Task: {task_id}[/]")
        else:
            console.print("[green]Update request accepted.[/]")
