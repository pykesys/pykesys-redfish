from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def health_color(health: str | None) -> str:
    mapping = {"OK": "green", "Warning": "yellow", "Critical": "red"}
    return mapping.get(health or "", "white")


def power_color(state: str | None) -> str:
    if state == "On":
        return "green"
    if state in ("PoweringOn", "PoweringOff"):
        return "yellow"
    return "dim"


def system_table(summary: dict) -> Table:
    t = Table(box=box.ROUNDED, show_header=False, title="System")
    t.add_column("Field", style="bold")
    t.add_column("Value")
    rows = [
        ("ID", summary.get("id")),
        ("Hostname", summary.get("hostname")),
        ("Manufacturer", summary.get("manufacturer")),
        ("Model", summary.get("model")),
        ("Serial", summary.get("serial_number")),
        ("BIOS", summary.get("bios_version")),
        ("Power", f"[{power_color(summary.get('power_state'))}]{summary.get('power_state')}[/]"),
        ("Health", f"[{health_color(summary.get('health'))}]{summary.get('health')}[/]"),
        ("RAM (GiB)", str(summary.get("total_memory_gib"))),
        ("CPUs", str(summary.get("processor_count"))),
        ("CPU Model", summary.get("processor_model")),
    ]
    for label, value in rows:
        t.add_row(label, value or "—")
    return t


def log_table(entries: list[dict]) -> Table:
    t = Table(box=box.SIMPLE, title="Log Entries")
    t.add_column("ID", style="dim")
    t.add_column("Created")
    t.add_column("Severity")
    t.add_column("Message")
    for e in entries:
        sev = e.get("Severity", "")
        color = {"OK": "green", "Warning": "yellow", "Critical": "red"}.get(sev, "white")
        t.add_row(
            str(e.get("Id", "")),
            e.get("Created", ""),
            f"[{color}]{sev}[/]",
            e.get("Message", ""),
        )
    return t


def firmware_table(members: list[dict]) -> Table:
    t = Table(box=box.SIMPLE, title="Firmware Inventory")
    t.add_column("ID")
    t.add_column("Name")
    t.add_column("Version")
    t.add_column("Updateable")
    for m in members:
        t.add_row(
            m.get("Id", ""),
            m.get("Name", ""),
            m.get("Version", ""),
            "Yes" if m.get("Updateable") else "No",
        )
    return t


def accounts_table(accounts: list[dict]) -> Table:
    t = Table(box=box.SIMPLE, title="Accounts")
    t.add_column("ID")
    t.add_column("Username")
    t.add_column("Role")
    t.add_column("Enabled")
    for a in accounts:
        enabled = "[green]Yes[/]" if a.get("Enabled") else "[dim]No[/]"
        t.add_row(
            str(a.get("Id", "")),
            a.get("UserName", ""),
            a.get("RoleId", ""),
            enabled,
        )
    return t


def fleet_table(results: list[dict]) -> Table:
    t = Table(box=box.SIMPLE, title="Fleet Inventory")
    t.add_column("Host")
    t.add_column("Hostname")
    t.add_column("Model")
    t.add_column("Serial")
    t.add_column("BIOS")
    t.add_column("RAM (GiB)")
    t.add_column("CPUs")
    t.add_column("Power")
    t.add_column("Health")
    t.add_column("Error")
    for r in results:
        err = r.get("error", "")
        t.add_row(
            r.get("host", ""),
            r.get("hostname", "") or "—",
            r.get("model", "") or "—",
            r.get("serial_number", "") or "—",
            r.get("bios_version", "") or "—",
            str(r.get("total_memory_gib") or "") or "—",
            str(r.get("processor_count") or "") or "—",
            f"[{power_color(r.get('power_state'))}]{r.get('power_state', '—')}[/]",
            f"[{health_color(r.get('health'))}]{r.get('health', '—')}[/]",
            f"[red]{err}[/]" if err else "",
        )
    return t
