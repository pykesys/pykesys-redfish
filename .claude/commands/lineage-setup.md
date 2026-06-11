# /lineage-setup — Constitutional Lineage Setup

Creates or updates `.claude/LAW-LINEAGE.md` for this project. Shows the existing file if present,
collects or confirms all required fields, writes the file, then syncs skill files from law-mother
(daughter projects only). Works for both law-mother and daughter project setup.

**Argument**: `$ARGUMENTS` — optional role hint: `mother` or `daughter`. If omitted: detected
from existing file or asked.

Examples:
```
/project:lineage-setup
/project:lineage-setup mother
/project:lineage-setup daughter
```

---

## Table of Contents

- [What This Command Does](#what-this-command-does)
- [Step 1 — Detect Current State](#step-1--detect-current-state)
- [Step 2 — Establish Role](#step-2--establish-role)
- [Step 3 — Collect / Confirm Fields](#step-3--collect--confirm-fields)
- [Step 4 — Write LAW-LINEAGE.md](#step-4--write-law-lineagemd)
- [Step 5 — Update CLAUDE.md Lineage Declaration](#step-5--update-claudemd-lineage-declaration-daughter-only)
- [Step 6 — File Sync](#step-6--file-sync)
- [Step 7 — Validate and Report](#step-7--validate-and-report)
- [File Sync Reference](#file-sync-reference)

---

## What This Command Does

LAW-LINEAGE.md is the machine-readable lineage declaration for every project in the constitutional
lineage. Skills (`/ladder`, `/repatriation`, `/daughter-cascade`) read it directly — it is the
single source of truth for role, law-mother path, adoption model, and lineage dates.

This command makes setup correct and repeatable:
- **Law-mother**: declares `role: mother`, ensures no daughter fields present
- **Daughter**: collects all required fields, writes the file, syncs skill files from law-mother,
  ensures bootstrap files exist, copies constitutional core (full adoption only)

The command is interactive — it shows the current state at each step and asks before changing.

[↑ Back to Top](#table-of-contents)

---

## Step 1 — Detect Current State

Read the current file if it exists:
```bash
cat .claude/LAW-LINEAGE.md 2>/dev/null || echo "NOT FOUND"
```

**If found**: display the full contents, then ask:
> "LAW-LINEAGE.md found (shown above). Does this need editing? [yes/no]"
>
> If no: skip to Step 6 (still run file sync to check for updates). Skip Steps 2–5.
> If yes: proceed to Step 2 — all fields will be shown with current values for confirmation.

**If not found**: announce "No LAW-LINEAGE.md found — creating new one." Proceed to Step 2.

[↑ Back to Top](#table-of-contents)

---

## Step 2 — Establish Role

Determine role using this priority order:

1. **`$ARGUMENTS`** — if `mother` or `daughter` was passed, use it
2. **Existing file** — read `role:` field from `.claude/LAW-LINEAGE.md`
3. **Ask the human**:
   > "Is this project law-mother (the constitutional source) or a daughter (inherits by lineage)?
   > Enter: mother / daughter"

Record the role. It drives all subsequent steps.

[↑ Back to Top](#table-of-contents)

---

## Step 3 — Collect / Confirm Fields

Show each field with its current value (or the detected default). Ask to confirm or override.

### Mother fields

```
role:        mother                  [fixed — cannot change to daughter here]
project:     [basename $PWD]         [confirm or enter new value]
established: [from file | today]     [confirm or enter new value — format YYYY-MM-DD]
```

Example prompt:
> "project: [template-law-claude] — press Enter to confirm, or type new value:"

### Daughter fields

```
role:           daughter              [fixed]
project:        [basename $PWD]       [confirm or enter new value]
mother_path:    [from file | ?]       [required — relative path from this repo to law-mother]
mother_name:    [from file | ?]       [required — law-mother project name for display/fallback]
adoption_model: [from file | ?]       [required — lightweight or full]
adopted:        [from file | today]   [confirm or enter new value — format YYYY-MM-DD]
```

Field guidance (print when prompting):
- **mother_path**: relative path that resolves at runtime — e.g. `../template-law-claude`
  Must point to a directory containing `.claude/PROJECT_LAWS.md`. Verify:
  ```bash
  ls [mother_path]/.claude/PROJECT_LAWS.md
  ```
- **mother_name**: display name used in reports and fallback search — e.g. `template-law-claude`
  Usually matches the directory name of the law-mother repo.
- **adoption_model**:
  - `lightweight` — inherits laws by reference; no local `.init/` needed
  - `full` — owns `.init/` database and `law-manage.py`; can add laws; higher maintenance

All required fields must be set before proceeding. If the human declines to enter a required
field, halt with: "Cannot write LAW-LINEAGE.md — [field] is required."

[↑ Back to Top](#table-of-contents)

---

## Step 4 — Write LAW-LINEAGE.md

Construct the file content from confirmed fields and write it.

### Mother format

```markdown
---
role: mother
project: [project]
established: [established]
---

# LAW-LINEAGE — [project]

This file declares the constitutional lineage role of this project.

**role: mother** — This project is the constitutional source. It does not inherit from any parent.
It receives repatriated discoveries from its daughters. All daughters point here.

**established**: [established] — date the constitutional framework was initialized.

---

## Lineage Protocol

Daughters declare their lineage by placing `.claude/LAW-LINEAGE.md` in their repo:

```
role: daughter
project: [project-name]
mother_path: [relative path to this repo]
mother_name: [project]
adoption_model: lightweight | full
adopted: YYYY-MM-DD
```

Skills read this file directly — not `grep "Law-mother:" CLAUDE.md`.

**mother_path**: relative path from daughter to law-mother (runtime use — must resolve)
**mother_name**: display name and fallback lookup (used when path is temporarily unavailable)
**adoption_model**: `lightweight` (reference daughter) or `full` (constitutional fork)

---

**Law**: LAW 21 (Epiphany Repatriation) + META-LAW 1 (Lineage Transmission)
**Created**: [today]
```

### Daughter format

```markdown
---
role: daughter
project: [project]
mother_path: [mother_path]
mother_name: [mother_name]
adoption_model: [adoption_model]
adopted: [adopted]
---

# LAW-LINEAGE — [project]

This file declares the constitutional lineage of this project.

**role: daughter** — This project inherits constitutional governance from law-mother.
Skills read this file to locate law-mother, determine adoption model, and route repatriation.

**mother_path**: [mother_path] — relative path to law-mother (runtime use)
**mother_name**: [mother_name] — display name; used when path is temporarily unavailable
**adoption_model**: [adoption_model]
  - `lightweight`: inherits all laws by reference; no local `.init/` database
  - `full`: owns `.init/`, `law-manage.py`, and full constitutional machinery

**adopted**: [adopted]

---

**Law**: LAW 21 (Epiphany Repatriation) + META-LAW 1 (Lineage Transmission)
**Created**: [today] — via /project:lineage-setup
```

After writing, confirm by reading back:
```bash
cat .claude/LAW-LINEAGE.md
```

If the read-back does not match what was written, halt and report the discrepancy.

[↑ Back to Top](#table-of-contents)

---

## Step 5 — Update CLAUDE.md Lineage Declaration (Daughter only)

Skip this step for law-mother.

Check if the lineage declaration is present in `CLAUDE.md`:
```bash
grep "Law-mother:" CLAUDE.md 2>/dev/null
```

**If absent**: offer to add it.
> "No 'Law-mother:' declaration found in CLAUDE.md. Add 'Law-mother: [mother_path]'? [yes/no]"
>
> If yes: append to the appropriate section in CLAUDE.md (after the first `##` heading, or at top).

**If present**: verify it matches `mother_path` from LAW-LINEAGE.md:
```bash
CLAUDE_PATH=$(grep "Law-mother:" CLAUDE.md | awk '{print $2}')
LINEAGE_PATH=$(grep "^mother_path:" .claude/LAW-LINEAGE.md | awk '{print $2}')
```

If they differ: flag mismatch.
> "CLAUDE.md says 'Law-mother: [CLAUDE_PATH]' but LAW-LINEAGE.md says 'mother_path: [LINEAGE_PATH]'.
> Which is correct? [1] Keep CLAUDE.md value / [2] Keep LAW-LINEAGE.md value"
>
> Update the other file to match whichever is chosen.

[↑ Back to Top](#table-of-contents)

---

## Step 6 — File Sync

### Law-Mother

Step 6 is skipped for law-mother. Report:
> "This is law-mother — no upstream sync applicable. It is the source."

### Daughter

Resolve law-mother path and verify reachability:
```bash
MOTHER_PATH=$(grep "^mother_path:" .claude/LAW-LINEAGE.md | awk '{print $2}')
MOTHER_NAME=$(grep "^mother_name:" .claude/LAW-LINEAGE.md | awk '{print $2}')
ADOPTION_MODEL=$(grep "^adoption_model:" .claude/LAW-LINEAGE.md | awk '{print $2}')
ls "$MOTHER_PATH/.claude/PROJECT_LAWS.md" 2>/dev/null || echo "UNREACHABLE"
```

**If law-mother unreachable**: skip sync. Report:
> "Sync skipped — law-mother ($MOTHER_NAME) not reachable at $MOTHER_PATH.
> Re-run /project:lineage-setup when law-mother is accessible to complete file sync."

---

#### Category A — Skills (all daughters, always sync)

These files are owned by law-mother and should match it exactly. Daughters receive updates when
law-mother evolves — stale skill files mean stale behavior.

Files to check:

| File | Description |
|------|-------------|
| `.claude/commands/ladder.md` | Session coherence ladder |
| `.claude/commands/daughter-cascade.md` | Daughter cascade protocol |
| `.claude/commands/repatriation.md` | Repatriation router |
| `.claude/commands/lineage-setup.md` | This command (self-sync) |

For each file:
```bash
# Check existence
ls .claude/commands/[file] 2>/dev/null && echo "EXISTS" || echo "MISSING"

# Compare with law-mother
diff .claude/commands/[file] "$MOTHER_PATH/.claude/commands/[file]" 2>/dev/null \
  && echo "CURRENT" || echo "STALE"
```

**MISSING** → copy automatically, no prompt needed. Report: "Copied [file] from law-mother."
**STALE** → prompt:
> "Update .claude/commands/[file] from law-mother ($MOTHER_NAME)? (law-mother is newer) [yes/no]"
>
> If yes: copy. If no: leave as-is, note in final report.
**CURRENT** → no action.

---

#### Category B — Bootstrap Files (all daughters, existence check only)

These are daughter-owned. Check existence only — **never overwrite from law-mother**.
If missing, create from template.

| File | Template action if missing |
|------|--------------------------|
| `MEMORY.md` | Create with project-name header + identity stub |
| `.claude/SESSION_CONTEXT.md` | Create with constitutional state header |
| `docs/accretion.md` | Create with standard accretion log header |
| `.claude/EPIPHANIES.md` | Create with standard epiphany log header |

**MEMORY.md template**:
```markdown
# [project] Memory

## Project identity
- **Repo**: [project] — [one-line description — update this]
- **Branch**: [active branch]
- **Law-mother**: [mother_name] at [mother_path]

## Last significant change
[Date and summary — update at session end per LAW 19]
```

**SESSION_CONTEXT.md template**:
```markdown
# SESSION_CONTEXT — [project]

**Law-mother**: [mother_path]
**Constitutional state**: inherited from [mother_name] (30 laws, LAW 0-29)
**Adoption model**: [adoption_model]

## Current State
[Update at session end — LAW 0]

## Ladder Run Log
[/ladder writes entries here — proof of execution]

## History
[Session history accumulates here]
```

**docs/accretion.md template**:
```markdown
# Accretion Log — [project]

*Sedimentation record for [project]. Each meaningful session deposits a stratum.*

**Mandate**: LAW 26 — Cascade Coherence. Deposit before closing every meaningful session.

## Table of Contents
[TOC entries accumulate here]

---

## Strata

*[First stratum: adopted constitutional governance — deposit this at first session end]*
```

**EPIPHANIES.md template**:
```markdown
# EPIPHANIES — [project]

*Session arcs and recognition moments. All epiphanies logged. No curation (LAW 16).*

---

## Session Arcs

*[First arc accumulates here]*
```

---

#### Category C — Constitutional Core (full adoption only, initial setup)

Only applies when `adoption_model: full`. Only copy files that **do not yet exist** in the
daughter — these become the daughter's own constitutional database to maintain.

**Do not overwrite existing Category C files** — the daughter may have added laws or customized
its constitution.

| File | Copy if absent? | Notes |
|------|----------------|-------|
| `.claude/PROJECT_LAWS.md` | Yes | Daughter's starting constitution — will be extended |
| `.claude/CODEX.md` | Yes | Law registry — daughter extends this |
| `.claude/CONSTITUTION-VERSION.md` | Yes | Version tracker — daughter maintains |
| `.claude/FOUNDATIONS.md` | Yes | Core philosophy — daughter may reference or fork |
| `.claude/bin/law-manage.py` | Yes | Tool — copy always; see update rule below |
| `.claude/.init/` (full dir) | Yes | All 43 units — starting enforcement database |
| `.claude/hooks/` | Yes | Session loader hooks |
| `.claude/.hooks/` | Yes | Install hook scripts |

**law-manage.py update rule** (applies even if file exists):
```bash
diff .claude/bin/law-manage.py "$MOTHER_PATH/.claude/bin/law-manage.py" 2>/dev/null \
  && echo "CURRENT" || echo "STALE"
```
If STALE: prompt to update. It is a tool, not constitutional data — safe to update without
losing daughter state.

After copying Category C:
```bash
python3 .claude/bin/law-manage.py regenerate
```
This rebuilds derived enforcement files from the copied init units.

---

#### Sync Report Format

Print at end of Step 6:
```
File Sync Report ($MOTHER_NAME → [project]):
  Category A — Skills:
    .claude/commands/ladder.md            [CURRENT | UPDATED | COPIED | SKIPPED]
    .claude/commands/daughter-cascade.md  [CURRENT | UPDATED | COPIED | SKIPPED]
    .claude/commands/repatriation.md      [CURRENT | UPDATED | COPIED | SKIPPED]
    .claude/commands/lineage-setup.md     [CURRENT | UPDATED | COPIED | SKIPPED]

  Category B — Bootstrap:
    MEMORY.md                             [EXISTS | CREATED]
    .claude/SESSION_CONTEXT.md            [EXISTS | CREATED]
    docs/accretion.md                     [EXISTS | CREATED]
    .claude/EPIPHANIES.md                 [EXISTS | CREATED]

  Category C — Constitutional Core (full adoption only):
    .claude/PROJECT_LAWS.md               [EXISTS (no overwrite) | COPIED]
    .claude/CODEX.md                      [EXISTS (no overwrite) | COPIED]
    .claude/CONSTITUTION-VERSION.md       [EXISTS (no overwrite) | COPIED]
    .claude/FOUNDATIONS.md                [EXISTS (no overwrite) | COPIED]
    .claude/bin/law-manage.py             [CURRENT | UPDATED | COPIED]
    .claude/.init/ (43 units)             [EXISTS (no overwrite) | COPIED]
    .claude/hooks/                        [EXISTS (no overwrite) | COPIED]
    .claude/.hooks/                       [EXISTS (no overwrite) | COPIED]
```

[↑ Back to Top](#table-of-contents)

---

## Step 7 — Validate and Report

### All roles

Read back the file and confirm all required fields are present:
```bash
cat .claude/LAW-LINEAGE.md
ROLE=$(grep "^role:" .claude/LAW-LINEAGE.md | awk '{print $2}')
```

For **mother**: confirm `role`, `project`, `established` all present.
For **daughter**: confirm `role`, `project`, `mother_path`, `mother_name`, `adoption_model`, `adopted` all present.

Missing field = FAIL. Report which field is missing.

### Full adoption daughter only

Run constitutional validation:
```bash
python3 .claude/bin/law-manage.py validate
```
Any output beyond "All invariants satisfied" = FAIL — run `law-manage.py regenerate` and retry.

### Final Summary

```
⚖️  Lineage Setup Complete
==========================
Role:           [mother | daughter]
Project:        [project]

[Mother fields:]
  Established:  [established]

[Daughter fields:]
  Law-mother:   [mother_name] at [mother_path]
  Model:        [lightweight | full]
  Adopted:      [adopted]

LAW-LINEAGE.md:    ✓ written and verified
CLAUDE.md:         ✓ declaration present | ⚠ absent — add manually | ✓ updated
File sync:         [N CURRENT, M UPDATED/COPIED, K MISSING(skipped)]
                   [Sync skipped — law-mother unreachable] (if applicable)
Constitutional DB: ✓ valid | ⚠ skipped (lightweight) | FAIL (detail)
==========================
Next step: run /project:ladder to verify full session coherence.
```

[↑ Back to Top](#table-of-contents)

---

## File Sync Reference

| File | Category | Sync behavior | Applies to |
|------|----------|--------------|------------|
| `.claude/commands/ladder.md` | A — Skills | MISSING: auto-copy; STALE: prompt | All daughters |
| `.claude/commands/daughter-cascade.md` | A — Skills | MISSING: auto-copy; STALE: prompt | All daughters |
| `.claude/commands/repatriation.md` | A — Skills | MISSING: auto-copy; STALE: prompt | All daughters |
| `.claude/commands/lineage-setup.md` | A — Skills | MISSING: auto-copy; STALE: prompt | All daughters |
| `MEMORY.md` | B — Bootstrap | MISSING: create from template; never overwrite | All daughters |
| `.claude/SESSION_CONTEXT.md` | B — Bootstrap | MISSING: create from template; never overwrite | All daughters |
| `docs/accretion.md` | B — Bootstrap | MISSING: create from template; never overwrite | All daughters |
| `.claude/EPIPHANIES.md` | B — Bootstrap | MISSING: create from template; never overwrite | All daughters |
| `.claude/PROJECT_LAWS.md` | C — Core | MISSING: copy from law-mother; never overwrite | Full adoption |
| `.claude/CODEX.md` | C — Core | MISSING: copy from law-mother; never overwrite | Full adoption |
| `.claude/CONSTITUTION-VERSION.md` | C — Core | MISSING: copy from law-mother; never overwrite | Full adoption |
| `.claude/FOUNDATIONS.md` | C — Core | MISSING: copy from law-mother; never overwrite | Full adoption |
| `.claude/bin/law-manage.py` | C — Core | STALE: prompt to update (tool, not data) | Full adoption |
| `.claude/.init/` (43 units) | C — Core | MISSING: copy entire directory; never overwrite | Full adoption |
| `.claude/hooks/` | C — Core | MISSING: copy; never overwrite | Full adoption |
| `.claude/.hooks/` | C — Core | MISSING: copy; never overwrite | Full adoption |

**Key distinction**:
- Category A files (skills): law-mother owns them — daughters always receive updates
- Category B files (bootstrap): daughter owns them — only created from template, never synced
- Category C files (core): daughter owns them after initial copy — only law-manage.py can be updated

[↑ Back to Top](#table-of-contents)

---

**Law**: LAW 21 (Epiphany Repatriation) + META-LAW 1 (Lineage Transmission) + LAW 26 (Cascade Coherence)
**Created**: 2026-04-10 — Phase 4 lineage formalization
**Pair**: `.claude/LAW-LINEAGE.md` — the file this command manages
**Also see**: `ADOPTION.md` — complete adoption guide; `.claude/commands/daughter-cascade.md`
