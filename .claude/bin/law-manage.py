#!/usr/bin/env python3
"""
law-manage.py — Constitutional Law Management Tool
===================================================
Source: .claude/bin/law-manage.py

The single point of entry for all constitutional CRUD operations.
Claude uses this. Users use this. Pre-commit uses this.

Source of truth: .claude/.init/law.N files
Derived:         CONSTITUTION-VERSION.md counts
                 .claude/.init/meta.init list
                 .claude/hooks/session-loader.sh count refs
Preferences:     .claude/project.conf (project-level)
                 .claude/prefs.d/*.conf (drop-in extensions)

Usage:
  law-manage.py list                    # all laws: number, name, status
  law-manage.py show <N>               # full record + relations
  law-manage.py relations <N>          # dependency graph for one law
  law-manage.py graph                  # full system inter-relation map
  law-manage.py search <term>          # find laws by keyword
  law-manage.py validate               # check derived files match source
  law-manage.py regenerate             # regenerate derived files from source
  law-manage.py add <N> <name>         # create new law scaffold
  law-manage.py delete <N>             # delete a law (requires confirmation)
  law-manage.py prefs list             # show all active (non-default) preferences
  law-manage.py prefs show             # show full config with defaults indicated
  law-manage.py prefs get <key>        # get a single value (e.g. git.AUTO_PUSH)
  law-manage.py prefs set <key> <val>  # set a preference (e.g. git.AUTO_PUSH false)
  law-manage.py prefs unset <key>      # reset a preference to default (empty/false)

References:
  PROJECT_LAWS.md § LAW 18 — Law Database Integrity
  .claude/.init/law.18
  .claude/.init/meta.init
  .claude/project.conf  — project preference layer
  .claude/prefs.d/      — drop-in preference extensions
"""

import os
import sys
import re
import configparser
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────
# PATHS — relative to this script's location (.claude/bin/)
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
CLAUDE_DIR = SCRIPT_DIR.parent          # .claude/
REPO_ROOT  = CLAUDE_DIR.parent          # repo root

INIT_DIR            = CLAUDE_DIR / ".init"
CONSTITUTION_VER    = CLAUDE_DIR / "CONSTITUTION-VERSION.md"
META_INIT           = INIT_DIR / "meta.init"
SESSION_LOADER      = CLAUDE_DIR / "hooks" / "session-loader.sh"
PROJECT_LAWS        = CLAUDE_DIR / "PROJECT_LAWS.md"
SESSION_CONTEXT     = CLAUDE_DIR / "SESSION_CONTEXT.md"
CLAUDE_MD           = REPO_ROOT / "CLAUDE.md"
PROJECT_CONF        = CLAUDE_DIR / "project.conf"
PREFS_D             = CLAUDE_DIR / "prefs.d"

# ─────────────────────────────────────────────────────────────────
# DATA LAYER — parse .init/ files
# ─────────────────────────────────────────────────────────────────

def parse_init_file(path: Path) -> Dict:
    """Parse a .init/law.N service unit file.

    Returns a dict with all key=value pairs from the file.
    Section-scoped keys stored as Section.Key (e.g., Service.OnBoot).
    Metadata stored under _ prefix keys.
    """
    record = {"_path": str(path), "_raw_sections": []}
    current_section = None

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            # Section header [SectionName]
            if line.startswith("[") and line.endswith("]") and len(line) > 2:
                current_section = line[1:-1]
                record["_raw_sections"].append(current_section)
                continue
            # Skip comments and blank lines for key parsing
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Key=Value
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip()
                if key:
                    # Top-level (no section) or section-scoped
                    full_key = f"{current_section}.{key}" if current_section else key
                    record[full_key] = value
                    # Also store bare key for easy lookup (section wins if conflict)
                    if key not in record:
                        record[key] = value

    return record


def load_all_units() -> List[Dict]:
    """Load all constitutional unit files from .init/ directory.

    Loads law.N, meta-law.N, up.N files. Skips meta.init and hidden files.
    Returns list sorted by type then number.
    """
    units = []
    if not INIT_DIR.exists():
        return units

    for path in INIT_DIR.iterdir():
        name = path.name
        if name == "meta.init" or name.startswith(".") or not path.is_file():
            continue

        record = parse_init_file(path)
        record["_file"] = name

        if name.startswith("law."):
            suffix = name[4:]
            record["_type"] = "law"
            record["_num"] = int(suffix) if suffix.isdigit() else suffix
        elif name.startswith("meta-law."):
            suffix = name[9:]
            record["_type"] = "meta-law"
            record["_num"] = suffix
        elif name.startswith("up."):
            suffix = name[3:]
            record["_type"] = "up"
            record["_num"] = int(suffix) if suffix.isdigit() else suffix
        else:
            record["_type"] = "other"
            record["_num"] = name

        units.append(record)

    # Sort: laws numerically, then meta-laws, then ups
    def sort_key(r):
        t = r["_type"]
        n = r["_num"]
        order = {"law": 0, "meta-law": 1, "up": 2, "other": 3}
        return (order.get(t, 9), int(n) if str(n).isdigit() else str(n))

    return sorted(units, key=sort_key)


def get_law_units(units: List[Dict]) -> List[Dict]:
    return [r for r in units if r["_type"] == "law"]


def parse_touches(touches_str: str) -> Dict[str, List[str]]:
    """Parse Touches= field value.

    Format: hooks:file1,file2|docs:file1,file2|laws:LAW N,LAW M|bin:name
    Returns dict with keys: hooks, docs, laws, bin (each a list of strings).
    """
    result: Dict[str, List[str]] = {"hooks": [], "docs": [], "laws": [], "bin": []}
    if not touches_str or touches_str.strip().lower() in ("none", ""):
        return result

    for category in touches_str.split("|"):
        category = category.strip()
        if ":" not in category:
            continue
        cat_name, _, values = category.partition(":")
        cat_name = cat_name.strip().lower()
        values = values.strip()
        if not values or values.lower() == "none":
            continue
        items = [v.strip() for v in values.split(",") if v.strip() and v.strip().lower() != "none"]
        if cat_name in result:
            result[cat_name] = items

    return result


def display_name(record: Dict) -> str:
    """Return human-readable name for a unit record."""
    t = record["_type"]
    n = record["_num"]
    # Name field may be top-level or under Unit section
    name = record.get("Name", record.get("Unit.Name", "?"))
    if t == "law":
        return f"LAW {n}: {name}"
    elif t == "meta-law":
        return f"META-LAW {n}: {name}"
    elif t == "up":
        return f"UP {n}: {name}"
    return f"{record['_file']}: {name}"


def short_id(record: Dict) -> str:
    """Return short identifier (e.g. 'LAW 17', 'META-LAW 0', 'UP 3')."""
    t = record["_type"]
    n = record["_num"]
    if t == "law":
        return f"LAW {n}"
    elif t == "meta-law":
        return f"META-LAW {n}"
    elif t == "up":
        return f"UP {n}"
    return record["_file"]


# ─────────────────────────────────────────────────────────────────
# VALIDATE — check derived files match .init/ source layer
# ─────────────────────────────────────────────────────────────────

def cmd_validate(args) -> int:
    """Validate all derived files are consistent with .init/ source.

    Checks:
      1. Law count in CONSTITUTION-VERSION.md matches .init/law.N count
      2. Law count in session-loader.sh matches
      3. Law count in meta.init matches
      4. Every law.N in meta.init has a corresponding .init/law.N file
      5. Touches= field present on all law units (warning only)
    """
    print("⚖️  Constitutional Completeness Validation")
    print("─" * 52)

    units     = load_all_units()
    law_units = get_law_units(units)
    law_count = len(law_units)
    max_num   = max((r["_num"] for r in law_units), default=0)

    violations: List[str] = []
    warnings:   List[str] = []

    # ── 1. CONSTITUTION-VERSION.md ──────────────────────────────
    if CONSTITUTION_VER.exists():
        text = CONSTITUTION_VER.read_text(encoding="utf-8")
        m = re.search(r'\|\s*\*\*Constitutional Laws\*\*\s*\|\s*\*\*(\d+)\*\*', text)
        if m:
            cv_count = int(m.group(1))
            if cv_count != law_count:
                violations.append(
                    f"CONSTITUTION-VERSION.md: {cv_count} laws "
                    f"(source has {law_count})"
                )
            else:
                print(f"✓ CONSTITUTION-VERSION.md  : {cv_count} laws")
        else:
            warnings.append("CONSTITUTION-VERSION.md: cannot parse law count")
    else:
        violations.append("CONSTITUTION-VERSION.md not found")

    # ── 2. session-loader.sh ────────────────────────────────────
    if SESSION_LOADER.exists():
        text = SESSION_LOADER.read_text(encoding="utf-8")
        m = re.search(r'CONSTITUTIONAL LAWS:\s*(\d+)\s*\(LAW 0-(\d+)\)', text)
        if m:
            sl_count = int(m.group(1))
            sl_max   = int(m.group(2))
            if sl_count != law_count or sl_max != max_num:
                violations.append(
                    f"session-loader.sh: {sl_count} laws (LAW 0-{sl_max}) "
                    f"(source: {law_count} laws LAW 0-{max_num})"
                )
            else:
                print(f"✓ session-loader.sh        : {sl_count} laws (LAW 0-{sl_max})")
        else:
            warnings.append("session-loader.sh: cannot parse CONSTITUTIONAL LAWS line")
    else:
        warnings.append("session-loader.sh not found (skipped)")

    # ── 3. meta.init list ───────────────────────────────────────
    if META_INIT.exists():
        text = META_INIT.read_text(encoding="utf-8")
        meta_entries = re.findall(r'#\s*\[\d+\]\s+law\.(\d+)', text)
        meta_count = len(meta_entries)
        if meta_count != law_count:
            violations.append(
                f"meta.init: {meta_count} law entries "
                f"(source has {law_count})"
            )
        else:
            print(f"✓ meta.init                : {meta_count} law entries")

        # Check each listed law.N exists
        for num_str in meta_entries:
            law_path = INIT_DIR / f"law.{num_str}"
            if not law_path.exists():
                violations.append(
                    f"meta.init lists law.{num_str} but "
                    f".init/law.{num_str} does not exist"
                )
    else:
        violations.append("meta.init not found")

    # ── 4. Touches= field presence (warning) ─────────────────────
    missing_touches = [r["_file"] for r in law_units if not r.get("Touches", "")]
    if missing_touches:
        warnings.append(
            f"Touches= missing from: {', '.join(missing_touches)}"
        )
    else:
        print(f"✓ Touches= field           : present on all {law_count} law units")

    # ── Report ───────────────────────────────────────────────────
    print()
    if violations:
        print(f"✗ {len(violations)} VIOLATION(S) — constitutional drift detected:")
        for v in violations:
            print(f"    ✗ {v}")
        if warnings:
            print()
            print(f"⚠  {len(warnings)} WARNING(S):")
            for w in warnings:
                print(f"    ⚠  {w}")
        print()
        print("Run:  python3 .claude/bin/law-manage.py regenerate")
        return 1
    else:
        if warnings:
            print(f"⚠  {len(warnings)} WARNING(S) (non-blocking):")
            for w in warnings:
                print(f"    ⚠  {w}")
            print()
        print("✓ All constitutional invariants satisfied")
        return 0


# ─────────────────────────────────────────────────────────────────
# REGENERATE — update derived files from .init/ source
# ─────────────────────────────────────────────────────────────────

def cmd_regenerate(args) -> int:
    """Regenerate all derived files from .init/ source layer.

    Updates:
      - session-loader.sh  CONSTITUTIONAL LAWS count line
      - CONSTITUTION-VERSION.md  law count cell
      - meta.init  law unit block and total count
    """
    print("⚖️  Constitutional Regeneration")
    print("─" * 52)

    units     = load_all_units()
    law_units = get_law_units(units)
    law_count = len(law_units)
    max_num   = max((r["_num"] for r in law_units), default=0)
    meta_count = len([r for r in units if r["_type"] == "meta-law"])
    up_count   = len([r for r in units if r["_type"] == "up"])
    total      = len(units)

    changed: List[str] = []

    # ── 1. session-loader.sh ────────────────────────────────────
    if SESSION_LOADER.exists():
        text = SESSION_LOADER.read_text(encoding="utf-8")
        new_text = re.sub(
            r'CONSTITUTIONAL LAWS:\s*\d+\s*\(LAW 0-\d+\)',
            f'CONSTITUTIONAL LAWS: {law_count} (LAW 0-{max_num})',
            text
        )
        if new_text != text:
            SESSION_LOADER.write_text(new_text, encoding="utf-8")
            print(f"✓ session-loader.sh → CONSTITUTIONAL LAWS: {law_count} (LAW 0-{max_num})")
            changed.append("session-loader.sh")
        else:
            print(f"  session-loader.sh already current")

    # ── 2. CONSTITUTION-VERSION.md ──────────────────────────────
    if CONSTITUTION_VER.exists():
        text = CONSTITUTION_VER.read_text(encoding="utf-8")
        # Update law count cell: | **Constitutional Laws** | **N** | LAW 0–M |
        new_text = re.sub(
            r'(\|\s*\*\*Constitutional Laws\*\*\s*\|\s*\*\*)\d+(\*\*\s*\|\s*LAW 0–)\d+',
            f'\\g<1>{law_count}\\g<2>{max_num}',
            text
        )
        if new_text != text:
            CONSTITUTION_VER.write_text(new_text, encoding="utf-8")
            print(f"✓ CONSTITUTION-VERSION.md → {law_count} laws (LAW 0-{max_num})")
            changed.append("CONSTITUTION-VERSION.md")
        else:
            print(f"  CONSTITUTION-VERSION.md already current")

    # ── 3. meta.init ────────────────────────────────────────────
    if META_INIT.exists():
        text = META_INIT.read_text(encoding="utf-8")

        # Rebuild law unit block
        law_lines = []
        for record in sorted(law_units, key=lambda r: r["_num"]):
            n    = record["_num"]
            name = record.get("Name", record.get("Unit.Name", "?"))
            law_lines.append(f"# [{n}] law.{n}   {name}")
        new_block = "\n".join(law_lines)

        # Replace existing law block (between header dash line and meta-law section)
        new_text = re.sub(
            r'(# \[LAW UNITS\][^\n]*\n# ─+\n)(.*?)(#\n# \[META-LAW UNITS\])',
            lambda m: m.group(1) + new_block + "\n" + m.group(3),
            text,
            flags=re.DOTALL
        )

        # Update header: (N total, LAW 0-M)
        new_text = re.sub(
            r'(# \[LAW UNITS\] — Constitutional Laws \()\d+( total, LAW 0-)\d+(\))',
            f'\\g<1>{law_count}\\g<2>{max_num}\\g<3>',
            new_text
        )

        # Update total count line
        new_text = re.sub(
            r'(# Total:\s+)\d+( units \()\d+( laws \+ )\d+( meta-laws \+ )\d+( UPs \+ this loader\))',
            f'\\g<1>{total}\\g<2>{law_count}\\g<3>{meta_count}\\g<4>{up_count}\\g<5>',
            new_text
        )

        if new_text != text:
            META_INIT.write_text(new_text, encoding="utf-8")
            print(f"✓ meta.init → {law_count} law entries, {total} total units")
            changed.append("meta.init")
        else:
            print(f"  meta.init already current")

    print()
    if changed:
        print(f"Regenerated: {', '.join(changed)}")
        print("Run: python3 .claude/bin/law-manage.py validate   — to confirm")
    else:
        print("All derived files already current — no changes made")

    return 0


# ─────────────────────────────────────────────────────────────────
# LIST — show all constitutional units
# ─────────────────────────────────────────────────────────────────

def cmd_list(args) -> int:
    """List all constitutional units with status indicators."""
    units     = load_all_units()
    law_units = get_law_units(units)
    meta_units = [r for r in units if r["_type"] == "meta-law"]
    up_units   = [r for r in units if r["_type"] == "up"]

    law_count = len(law_units)
    print(f"⚖️  Constitutional Law Database")
    print(f"   {len(law_units)} Laws  |  {len(meta_units)} META-LAWs  |  {len(up_units)} UPs  |  {len(units)} total units")
    print("─" * 60)

    if law_units:
        print("CONSTITUTIONAL LAWS")
        for r in sorted(law_units, key=lambda x: x["_num"]):
            name = r.get("Name", r.get("Unit.Name", "?"))
            has_touches = bool(r.get("Touches", ""))
            marker = "◈" if has_touches else "○"
            print(f"  {marker} LAW {r['_num']:>2}:  {name}")

    if meta_units:
        print("\nMETA-LAWS")
        for r in meta_units:
            name = r.get("Name", r.get("Unit.Name", "?"))
            has_touches = bool(r.get("Touches", ""))
            marker = "◈" if has_touches else "○"
            print(f"  {marker} META-LAW {r['_num']}: {name}")

    if up_units:
        print("\nUNIVERSAL PRINCIPLES")
        for r in sorted(up_units, key=lambda x: x["_num"]):
            name = r.get("Name", r.get("Unit.Name", "?"))
            has_touches = bool(r.get("Touches", ""))
            marker = "◈" if has_touches else "○"
            print(f"  {marker} UP {r['_num']}: {name}")

    print()
    print("◈ = Touches= field present   ○ = Touches= field missing")
    return 0


# ─────────────────────────────────────────────────────────────────
# SHOW — display a single unit record
# ─────────────────────────────────────────────────────────────────

def cmd_show(args) -> int:
    """Show full record for a single constitutional unit."""
    units  = load_all_units()
    target = str(args.number).lower()

    record = None
    for r in units:
        if str(r["_num"]).lower() == target and r["_type"] == args.type:
            record = r
            break
    if not record:
        # Fallback: search across all types
        for r in units:
            if str(r["_num"]).lower() == target:
                record = r
                break

    if not record:
        print(f"✗ Not found: {args.type} {args.number}")
        return 1

    print(f"⚖️  {display_name(record)}")
    print(f"   Source: .claude/.init/{record['_file']}")
    print("─" * 60)

    skip = {"_path", "_file", "_type", "_num", "_raw_sections"}

    for key, val in record.items():
        if key in skip:
            continue
        if key == "Touches":
            print(f"\n  {key}:")
            for cat, items in parse_touches(val).items():
                if items:
                    print(f"    {cat:8}: {', '.join(items)}")
        elif len(val) > 72:
            print(f"\n  {key}:")
            # Simple word wrap at 76 chars
            words = val.split()
            line  = "    "
            for word in words:
                if len(line) + len(word) + 1 > 78:
                    print(line.rstrip())
                    line = "    " + word + " "
                else:
                    line += word + " "
            if line.strip():
                print(line.rstrip())
        else:
            print(f"  {key}: {val}")

    return 0


# ─────────────────────────────────────────────────────────────────
# RELATIONS — dependency graph for one unit
# ─────────────────────────────────────────────────────────────────

def cmd_relations(args) -> int:
    """Show outgoing and incoming relations for a constitutional unit."""
    units  = load_all_units()
    target = str(args.number).lower()

    record = None
    for r in units:
        if str(r["_num"]).lower() == target and r["_type"] == args.type:
            record = r
            break
    if not record:
        for r in units:
            if str(r["_num"]).lower() == target:
                record = r
                break

    if not record:
        print(f"✗ Not found: {args.number}")
        return 1

    print(f"⚖️  Relations: {display_name(record)}")
    print("─" * 60)

    # ── Outgoing (what this law touches) ─────────────────────────
    touches_str = record.get("Touches", "")
    if touches_str:
        touches = parse_touches(touches_str)
        has_any = any(touches.values())
        if has_any:
            print("  TOUCHES (outgoing):")
            for cat, items in touches.items():
                if items:
                    for item in items:
                        print(f"    → {cat}/{item}")
        else:
            print("  TOUCHES: (empty)")
    else:
        print("  TOUCHES: (no Touches= field present)")

    # ── Supports / related from unit fields ───────────────────────
    supports = record.get("Supports", record.get("Unit.Supports", ""))
    if supports:
        print(f"\n  SUPPORTS: {supports}")

    related = record.get("Install.Related", record.get("Related", ""))
    if related:
        print(f"  RELATED:  {related}")

    # ── Incoming (what references this law) ────────────────────────
    my_id = short_id(record)
    referencing: List[str] = []

    for r in units:
        if r is record:
            continue
        # Check Touches= laws field
        ts = parse_touches(r.get("Touches", ""))
        for law_ref in ts.get("laws", []):
            if my_id.lower() in law_ref.lower():
                dn = display_name(r)
                if dn not in referencing:
                    referencing.append(dn)
        # Check Supports= field
        sup = r.get("Supports", r.get("Unit.Supports", ""))
        if my_id in sup:
            dn = display_name(r)
            if dn not in referencing:
                referencing.append(dn)

    if referencing:
        print("\n  REFERENCED BY (incoming):")
        for ref in referencing:
            print(f"    ← {ref}")

    return 0


# ─────────────────────────────────────────────────────────────────
# GRAPH — full system inter-relation map
# ─────────────────────────────────────────────────────────────────

def cmd_graph(args) -> int:
    """Print full constitutional system inter-relation graph."""
    units = load_all_units()

    # Collect all referenced entities
    all_hooks: Dict[str, List[str]] = {}
    all_docs:  Dict[str, List[str]] = {}
    all_bins:  Dict[str, List[str]] = {}

    for r in units:
        ts = parse_touches(r.get("Touches", ""))
        name = short_id(r)
        for hook in ts.get("hooks", []):
            all_hooks.setdefault(hook, []).append(name)
        for doc in ts.get("docs", []):
            all_docs.setdefault(doc, []).append(name)
        for bn in ts.get("bin", []):
            all_bins.setdefault(bn, []).append(name)

    print("⚖️  Constitutional System Graph")
    print(f"   {len(units)} units  ·  {len(all_hooks)} hooks  ·  {len(all_docs)} docs  ·  {len(all_bins)} bin tools")
    print("─" * 60)

    if all_hooks:
        print("\nHOOKS")
        for hook, touching in sorted(all_hooks.items()):
            print(f"  {hook}")
            print(f"    ← {', '.join(touching)}")

    if all_docs:
        print("\nDOCS")
        for doc, touching in sorted(all_docs.items()):
            print(f"  {doc}")
            print(f"    ← {', '.join(touching)}")

    if all_bins:
        print("\nBIN TOOLS")
        for bn, touching in sorted(all_bins.items()):
            print(f"  {bn}")
            print(f"    ← {', '.join(touching)}")

    # Units with no Touches= field
    no_touches = [r for r in units if not r.get("Touches", "")]
    if no_touches:
        print(f"\n○  {len(no_touches)} units without Touches= field:")
        for r in no_touches:
            print(f"   {display_name(r)}")

    return 0


# ─────────────────────────────────────────────────────────────────
# SEARCH — find units by keyword
# ─────────────────────────────────────────────────────────────────

def cmd_search(args) -> int:
    """Search all constitutional unit fields for a keyword."""
    term  = args.term.lower()
    units = load_all_units()

    found = []
    for r in units:
        for key, val in r.items():
            if key.startswith("_"):
                continue
            if term in val.lower():
                found.append(r)
                break

    if not found:
        print(f"No units matching: '{args.term}'")
        return 0

    print(f"⚖️  Search: '{args.term}' — {len(found)} match(es)")
    print("─" * 50)
    for r in found:
        print(f"  {display_name(r)}")
    return 0


# ─────────────────────────────────────────────────────────────────
# ADD — create new law scaffold and regenerate derived files
# ─────────────────────────────────────────────────────────────────

def cmd_add(args) -> int:
    """Create a new law scaffold and update all derived files.

    Creates .init/law.N with standard scaffold, then runs regenerate
    to update CONSTITUTION-VERSION.md, meta.init, session-loader.sh.
    Claude still needs to:
      1. Fill in Why=, Context=, Wisdom=, Touches= in .init/law.N
      2. Add narrative section to PROJECT_LAWS.md
      3. Run law-manage.py validate to confirm
    """
    n    = args.number
    name = args.name
    path = INIT_DIR / f"law.{n}"

    if path.exists():
        print(f"✗ law.{n} already exists: {path}")
        return 1

    # Determine previous law number for After= field
    units     = load_all_units()
    law_units = get_law_units(units)
    prev_nums = [r["_num"] for r in law_units if isinstance(r["_num"], int) and r["_num"] < n]
    after_val = f"law.{max(prev_nums)}" if prev_nums else "activation"

    scaffold = f"""[Unit]
Name={name}
Number={n}
Why=
Context=
Wisdom=
Supports=
Touches=hooks:|docs:PROJECT_LAWS.md,CONSTITUTION-VERSION.md,SESSION_CONTEXT.md|laws:|bin:none
After={after_val}

[Requires]

[Service]
OnBoot=
OnSessionEnd=
OnChange=

[Compliance]
Test=
Violation=
Enforcement=

[Install]
WantedBy=all-sessions
Priority={n}
Codex=CODEX.md § LAW-{n}
Source=PROJECT_LAWS.md § LAW {n}
Related=
"""

    path.write_text(scaffold, encoding="utf-8")
    print(f"✓ Created scaffold: .claude/.init/law.{n}")
    print()
    print("Regenerating derived files...")
    result = cmd_regenerate(args)
    print()
    print(f"Next steps:")
    print(f"  1. Edit .claude/.init/law.{n}  — fill Why=, Context=, Wisdom=, Touches=")
    print(f"  2. Edit .claude/PROJECT_LAWS.md — add § LAW {n} narrative section")
    print(f"  3. python3 .claude/bin/law-manage.py validate")
    return result


# ─────────────────────────────────────────────────────────────────
# DELETE — remove a law (destructive, confirmation required)
# ─────────────────────────────────────────────────────────────────

def cmd_delete(args) -> int:
    """Delete a law unit file and regenerate derived files.

    Requires typing 'yes' to confirm unless --force is passed.
    Also removes from meta.init load order via regenerate.
    Note: Does NOT remove narrative from PROJECT_LAWS.md (manual step).
    """
    n    = args.number
    path = INIT_DIR / f"law.{n}"

    if not path.exists():
        print(f"✗ law.{n} not found")
        return 1

    record = parse_init_file(path)
    name   = record.get("Name", "?")

    if not args.force:
        print(f"Delete LAW {n}: {name}")
        print(f"  Source: .claude/.init/law.{n}")
        print(f"  This is irreversible. Manually remove § LAW {n} from PROJECT_LAWS.md after.")
        confirm = input("  Type 'yes' to confirm: ").strip()
        if confirm.lower() != "yes":
            print("Aborted.")
            return 0

    path.unlink()
    print(f"✓ Deleted: .claude/.init/law.{n}")
    print()
    print("Regenerating derived files...")
    result = cmd_regenerate(args)
    print()
    print(f"Reminder: manually remove § LAW {n} section from .claude/PROJECT_LAWS.md")
    return result


# ─────────────────────────────────────────────────────────────────
# PREFS — read/write .claude/project.conf preference layer
# ─────────────────────────────────────────────────────────────────

# Canonical defaults — what project.conf reverts to when unset.
# These mirror the defaults documented in project.conf comments.
PREF_DEFAULTS: Dict[str, Dict[str, str]] = {
    "git": {
        "COMMIT_ON_TASK_COMPLETE": "false",
        "AUTO_PUSH":               "false",
        "DEFAULT_BRANCH":          "main",
        "SIGN_COMMITS":            "false",
        "COMMIT_MSG_SCOPE":        "",
    },
    "cascade": {
        "EXTRA_TARGETS":           "",
        "VERBOSE":                 "false",
        "CONFIRM_EACH_STEP":       "false",
    },
    "ladder": {
        "EXTRA_RUNGS":             "",
        "REPORT_ONLY_RUNGS":       "",
        "SKIP_RUNGS":              "",
        "STATE_REPORT_MODE":       "summary",
    },
    "session": {
        "AUTO_MEMORY_UPDATE":      "true",
        "SHOW_PREFS_IN_STATE_REPORT": "true",
        "SHOW_RECENT_COMMITS":     "false",
        "SHOW_RECENT_COMMITS_COUNT": "10",
        "OUTPUT_TONE":             "",
    },
}


def load_prefs() -> configparser.ConfigParser:
    """Load project.conf and any prefs.d/*.conf drop-ins into one config.

    Merge order (later files override earlier):
      1. Canonical defaults (PREF_DEFAULTS)
      2. .claude/project.conf
      3. .claude/prefs.d/*.conf  (alphabetical order)

    Returns a ConfigParser with all merged values.
    """
    cfg = configparser.ConfigParser(
        interpolation=None,
        comment_prefixes=("#",),
        inline_comment_prefixes=("#",),
    )
    cfg.optionxform = str   # preserve key case (UPPER stays UPPER)

    # 1. Seed with defaults
    for section, keys in PREF_DEFAULTS.items():
        cfg.add_section(section)
        for k, v in keys.items():
            cfg.set(section, k, v)

    # 2. Load project.conf
    if PROJECT_CONF.exists():
        cfg.read(PROJECT_CONF, encoding="utf-8")

    # 3. Load prefs.d/*.conf drop-ins (sorted for determinism)
    if PREFS_D.exists():
        for drop_in in sorted(PREFS_D.glob("*.conf")):
            cfg.read(drop_in, encoding="utf-8")

    return cfg


def parse_pref_key(key: str) -> Tuple[str, str]:
    """Parse 'section.KEY' into (section, KEY). Raises ValueError if invalid."""
    if "." not in key:
        raise ValueError(
            f"Preference key must be section.KEY (e.g. git.AUTO_PUSH), got: {key!r}"
        )
    section, _, k = key.partition(".")
    return section.lower(), k.upper()


def cmd_prefs_list(args) -> int:
    """Show all preferences that differ from their defaults."""
    cfg = load_prefs()

    active: List[Tuple[str, str, str]] = []
    for section, defaults in PREF_DEFAULTS.items():
        if not cfg.has_section(section):
            continue
        for key, default_val in defaults.items():
            current = cfg.get(section, key, fallback=default_val)
            if current != default_val:
                active.append((section, key, current))

    print("⚙️  Active project preferences (non-default)")
    print("─" * 52)
    if not active:
        print("  (all preferences at default values)")
        print(f"\n  Config: {PROJECT_CONF}")
        return 0

    last_section = None
    for section, key, val in active:
        if section != last_section:
            print(f"\n  [{section}]")
            last_section = section
        display_val = val if val else "(empty)"
        print(f"    {key} = {display_val}")

    print(f"\n  Config: {PROJECT_CONF}")
    drop_ins = sorted(PREFS_D.glob("*.conf")) if PREFS_D.exists() else []
    if drop_ins:
        print(f"  Drop-ins ({len(drop_ins)}): " + ", ".join(d.name for d in drop_ins))
    return 0


def cmd_prefs_show(args) -> int:
    """Show full config with [default] or [set] indicator for each key."""
    cfg = load_prefs()

    print("⚙️  Full preference configuration")
    print("─" * 52)

    for section, defaults in PREF_DEFAULTS.items():
        print(f"\n[{section}]")
        for key, default_val in defaults.items():
            current = cfg.get(section, key, fallback=default_val)
            if current == default_val:
                marker = "  "
                note = f"(default: {default_val!r})" if default_val else "(default: empty)"
            else:
                marker = "★ "
                note = f"(default: {default_val!r})" if default_val else "(default: empty)"
            display_val = current if current else "(empty)"
            print(f"  {marker}{key} = {display_val}  {note}")

    print(f"\n★ = overridden from default")
    print(f"\nConfig: {PROJECT_CONF}")
    return 0


def cmd_prefs_get(args) -> int:
    """Get the current value of a single preference key."""
    try:
        section, key = parse_pref_key(args.key)
    except ValueError as e:
        print(f"✗ {e}")
        return 1

    cfg = load_prefs()

    if not cfg.has_section(section):
        print(f"✗ Unknown section: [{section}]")
        print(f"  Valid sections: {', '.join(PREF_DEFAULTS.keys())}")
        return 1

    default_val = PREF_DEFAULTS.get(section, {}).get(key)
    if default_val is None:
        print(f"✗ Unknown key: {key} in [{section}]")
        valid = list(PREF_DEFAULTS.get(section, {}).keys())
        print(f"  Valid keys in [{section}]: {', '.join(valid)}")
        return 1

    current = cfg.get(section, key, fallback=default_val)
    marker = "★" if current != default_val else " "
    print(f"{marker} {section}.{key} = {current!r}")
    if current != default_val:
        print(f"  (default: {default_val!r})")
    return 0


def cmd_prefs_set(args) -> int:
    """Set a preference in project.conf, creating the file if needed."""
    try:
        section, key = parse_pref_key(args.key)
    except ValueError as e:
        print(f"✗ {e}")
        return 1

    value = args.value

    if section not in PREF_DEFAULTS:
        print(f"✗ Unknown section: [{section}]")
        print(f"  Valid sections: {', '.join(PREF_DEFAULTS.keys())}")
        return 1

    if key not in PREF_DEFAULTS[section]:
        print(f"✗ Unknown key: {key} in [{section}]")
        valid = list(PREF_DEFAULTS[section].keys())
        print(f"  Valid keys in [{section}]: {', '.join(valid)}")
        return 1

    default_val = PREF_DEFAULTS[section][key]

    # Read project.conf as raw text to preserve comments
    if PROJECT_CONF.exists():
        raw = PROJECT_CONF.read_text(encoding="utf-8")
    else:
        print(f"✗ project.conf not found: {PROJECT_CONF}")
        print(f"  Create it from the template first.")
        return 1

    # Try to update the key in the [section] block
    # Pattern: inside the correct section, find KEY = <anything>
    section_pattern = re.compile(
        r'(\[' + re.escape(section) + r'\][^\[]*?)(' + re.escape(key) + r'\s*=\s*)(.*?)(\n)',
        re.DOTALL | re.IGNORECASE
    )

    new_raw, count = section_pattern.subn(
        lambda m: m.group(1) + m.group(2) + value + m.group(4),
        raw,
        count=1
    )

    if count == 0:
        print(f"✗ Could not find {key} in [{section}] section of project.conf")
        print(f"  The key may be missing from your project.conf.")
        print(f"  Regenerate from the template in law-mother.")
        return 1

    PROJECT_CONF.write_text(new_raw, encoding="utf-8")

    old_val = default_val
    # Try to read the old value from the original
    old_cfg = configparser.ConfigParser(interpolation=None, comment_prefixes=("#",))
    old_cfg.optionxform = str
    import io
    old_cfg.read_string(raw)
    if old_cfg.has_option(section, key):
        old_val = old_cfg.get(section, key)

    print(f"✓ {section}.{key}: {old_val!r} → {value!r}")
    print(f"  Written to: {PROJECT_CONF}")
    if value == default_val:
        print(f"  (value matches default — preference is now at default)")
    return 0


def cmd_prefs_unset(args) -> int:
    """Reset a preference to its default value."""
    try:
        section, key = parse_pref_key(args.key)
    except ValueError as e:
        print(f"✗ {e}")
        return 1

    if section not in PREF_DEFAULTS or key not in PREF_DEFAULTS[section]:
        print(f"✗ Unknown preference: {section}.{key}")
        return 1

    default_val = PREF_DEFAULTS[section][key]
    # Reuse set logic
    args.value = default_val
    result = cmd_prefs_set(args)
    if result == 0:
        print(f"  (reset to default: {default_val!r})")
    return result


def cmd_prefs(args) -> int:
    """Dispatch prefs subcommands."""
    dispatch = {
        "list":  cmd_prefs_list,
        "show":  cmd_prefs_show,
        "get":   cmd_prefs_get,
        "set":   cmd_prefs_set,
        "unset": cmd_prefs_unset,
    }
    fn = dispatch.get(args.prefs_cmd)
    if fn is None:
        print(f"✗ Unknown prefs command: {args.prefs_cmd}")
        return 1
    return fn(args)


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="law-manage.py",
        description=(
            "Constitutional Law Management Tool\n"
            "Source of truth: .claude/.init/law.N files\n"
            "Reference: PROJECT_LAWS.md § LAW 18"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p = sub.add_parser("list", help="List all constitutional units")
    p.set_defaults(func=cmd_list)

    # show
    p = sub.add_parser("show", help="Show a single unit record")
    p.add_argument("number", help="Unit number (e.g. 17, 0)")
    p.add_argument("--type", default="law", choices=["law", "meta-law", "up"],
                   help="Unit type (default: law)")
    p.set_defaults(func=cmd_show)

    # relations
    p = sub.add_parser("relations", help="Show dependency relations for a unit")
    p.add_argument("number", help="Unit number")
    p.add_argument("--type", default="law", choices=["law", "meta-law", "up"])
    p.set_defaults(func=cmd_relations)

    # graph
    p = sub.add_parser("graph", help="Show full system inter-relation graph")
    p.set_defaults(func=cmd_graph)

    # search
    p = sub.add_parser("search", help="Search all unit fields for a keyword")
    p.add_argument("term", help="Search term")
    p.set_defaults(func=cmd_search)

    # validate
    p = sub.add_parser("validate", help="Validate derived files match .init/ source")
    p.set_defaults(func=cmd_validate)

    # regenerate
    p = sub.add_parser("regenerate", help="Regenerate derived files from .init/ source")
    p.set_defaults(func=cmd_regenerate)

    # add
    p = sub.add_parser("add", help="Add a new law (scaffold + regenerate)")
    p.add_argument("number", type=int, help="Law number")
    p.add_argument("name",              help="Law name (quoted string)")
    p.set_defaults(func=cmd_add)

    # delete
    p = sub.add_parser("delete", help="Delete a law (destructive — confirmation required)")
    p.add_argument("number", type=int, help="Law number")
    p.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    p.set_defaults(func=cmd_delete)

    # prefs
    p_prefs = sub.add_parser("prefs", help="Read/write project preference layer")
    p_prefs.set_defaults(func=cmd_prefs)
    prefs_sub = p_prefs.add_subparsers(dest="prefs_cmd", required=True)

    pp = prefs_sub.add_parser("list",  help="Show all active (non-default) preferences")
    pp = prefs_sub.add_parser("show",  help="Show full config with defaults indicated")
    pp = prefs_sub.add_parser("get",   help="Get a single preference (e.g. git.AUTO_PUSH)")
    pp.add_argument("key", help="section.KEY (e.g. git.AUTO_PUSH)")
    pp = prefs_sub.add_parser("set",   help="Set a preference (e.g. git.AUTO_PUSH false)")
    pp.add_argument("key",   help="section.KEY (e.g. git.AUTO_PUSH)")
    pp.add_argument("value", help="New value")
    pp = prefs_sub.add_parser("unset", help="Reset a preference to its default")
    pp.add_argument("key", help="section.KEY to reset")

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
