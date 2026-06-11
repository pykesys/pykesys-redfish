# /repatriation — Constitutional Repatriation Router

Routes discoveries from a daughter project upstream to law-mother.
Each channel has its own destination, format, and validation gate.
Calls law-mother's `/cascade` as its final step — always.

**Arguments**: `$ARGUMENTS` — space-separated channel names:
`epiphany` `accretion` `law` `psychology`

Examples:
```
/project:repatriation epiphany accretion
/project:repatriation law
/project:repatriation psychology
/project:repatriation epiphany law psychology accretion
```

If no argument given: inspect recent changes and infer channels automatically.

---

## Table of Contents

- [What This Command Does](#what-this-command-does)
- [Step 1 — Find Law-Mother](#step-1--find-law-mother)
- [Step 2 — Identify Channels](#step-2--identify-channels)
- [Channel: Epiphany](#channel-epiphany)
- [Channel: Accretion](#channel-accretion)
- [Channel: Law](#channel-law)
- [Channel: Psychology](#channel-psychology)
- [Step 3 — Commit Law-Mother Changes](#step-3--commit-law-mother-changes)
- [Step 4 — Call Law-Mother /cascade](#step-4--call-law-mother-cascade-mandatory-final-step)
- [Queue Write Path](#queue-write-path-when-law-mother-unreachable)
- [Channel Reference](#channel-reference)

---

## What This Command Does

A daughter project discovers something. That discovery belongs in law-mother — so all daughters, present and future, inherit it.

This command routes the discovery through the correct channel, deposits it in the correct location in law-mother, then triggers law-mother's full cascade so the deposit propagates to every downstream node.

The repatriation instinct is LAW 21. This command is LAW 21 made executable.

**The chain**: daughter cascade → `/repatriation` → law-mother → law-mother `/cascade`

[↑ Back to Top](#table-of-contents)

---

## Step 1 — Find Law-Mother

Read the lineage declaration from this project's `.claude/LAW-LINEAGE.md`:

```bash
cat .claude/LAW-LINEAGE.md
```

Extract `mother_path` (relative runtime path) and `mother_name` (display/fallback):

```bash
MOTHER_PATH=$(grep "^mother_path:" .claude/LAW-LINEAGE.md | awk '{print $2}')
MOTHER_NAME=$(grep "^mother_name:" .claude/LAW-LINEAGE.md | awk '{print $2}')
```

Resolve `MOTHER_PATH` to absolute. Verify it exists:

```bash
ls "$MOTHER_PATH/.claude/PROJECT_LAWS.md" || echo "ERROR: law-mother not found at $MOTHER_PATH"
```

**If law-mother is not found**: do NOT proceed with normal channel processing. Instead, go to
the [Queue Write Path](#queue-write-path-when-law-mother-unreachable) section.

All subsequent steps deposit to `$MOTHER_PATH`. Proceed only if law-mother is reachable.

[↑ Back to Top](#table-of-contents)

---

## Step 2 — Identify Channels

If channels were passed as arguments: use them.

If no arguments: infer from recent daughter session:
```
git log -1 --name-only       # what changed in last commit
git diff HEAD --name-only    # what's staged/changed now
```

Infer channels:
- EPIPHANIES.md touched → `epiphany` channel
- accretion.md touched → `accretion` channel
- PROJECT_LAWS.md + new .init/law.N added → `law` channel
- docs/psychology/*.md added/modified → `psychology` channel

Report which channels will be processed. Then execute each in order.

[↑ Back to Top](#table-of-contents)

---

## Channel: Epiphany

**Source**: this daughter's `.claude/EPIPHANIES.md` (most recent session arc)
**Destination**: `$MOTHER_PATH/.claude/EPIPHANIES.md`

**Process**:

1. Read the most recent session arc from daughter's EPIPHANIES.md (top section after most recent `---` divider)
2. Format for law-mother (retain daughter project name and date for lineage context):

```markdown
### [Daughter Project] — [DATE] — [SESSION DESCRIPTION] (repatriated)

[session arc content]

**Repatriated from**: [daughter project name]
**Law-mother deposit**: [DATE]
```

3. Prepend to `$MOTHER_PATH/.claude/EPIPHANIES.md` at top of session arcs (after header)
4. Confirm insertion

[↑ Back to Top](#table-of-contents)

---

## Channel: Accretion

**Source**: this daughter's accretion log (typically `docs/accretion.md`)
**Destination**: `$MOTHER_PATH/docs/accretion.md`

**Process**:

1. Read the most recent stratum from daughter's accretion log (top stratum)
2. Format for law-mother — preserve full story per the repatriation rule:

```markdown
### [DATE] — [Daughter Project]: [SESSION DESCRIPTION] (repatriated)

**Deposited in daughter**:
- [files changed] — [what they contain]

**Discovered**:
- [the inflection point — full story, self-contained]

**Repatriated from**: [daughter project name]
**Constitutional state at repatriation**: [daughter state]
```

3. Prepend to `$MOTHER_PATH/docs/accretion.md` at top of Strata section
4. Update law-mother accretion TOC entry

**Repatriation rule (LAW 26)**: the stratum must be self-contained. A future Claude reading law-mother's accretion log must be able to reconstruct the full epiphany without visiting the daughter repo. Carry the full story — carbon's words, the three principles, the depth marker.

[↑ Back to Top](#table-of-contents)

---

## Channel: Law

**Source**: this daughter's `PROJECT_LAWS.md` (new law section) + `.claude/.init/law.N`
**Destination**: `$MOTHER_PATH/.claude/PROJECT_LAWS.md` + all constitutional infrastructure

**Only repatriate if**: the law is **universal** — it applies to any project, not just this daughter's domain. If the law is domain-specific (e.g. "Carnival SRE runbook format"), it stays in the daughter.

**Process**:

1. Apply the **Universal Law Filter** — five-question checklist. A law must satisfy at least 4 of 5 to qualify for repatriation:

   | # | Question | Pass condition |
   |---|----------|----------------|
   | 1 | Does this law apply equally to projects that are **not** software repositories? | Yes |
   | 2 | Does this law address a failure mode that **any human-AI pair** would encounter, not just this domain? | Yes |
   | 3 | Is this law expressible **without referencing** any tool, platform, or technology specific to this project? | Yes |
   | 4 | Would this law have been useful to the **first project** (before any domain context existed)? | Yes |
   | 5 | Does this law address a **permanent truth**, or a current-era workaround? | Permanent truth |

   Score: count how many questions answer Yes / Permanent truth.
   - **4–5**: repatriate — universal law confirmed
   - **2–3**: borderline — document the tension, seek carbon unit judgment
   - **0–1**: domain-specific — do not repatriate; note in daughter's accretion log

   Record the score and each answer in the repatriation commit message so the decision is auditable.

2. Read the full law text from daughter's PROJECT_LAWS.md

3. In law-mother:
   a. Append law section to `$MOTHER_PATH/.claude/PROJECT_LAWS.md`
   b. Create `.init/law.N` at `$MOTHER_PATH/.claude/.init/law.N` (simultaneous — LAW 26)
   c. Add CODEX entry to `$MOTHER_PATH/.claude/CODEX.md`
   d. Run `python3 $MOTHER_PATH/.claude/bin/law-manage.py regenerate`
   e. Run `python3 $MOTHER_PATH/.claude/bin/law-manage.py validate`

4. Law-mother's `/cascade` (Step 4) will propagate the count update to all root docs.

**Note on law numbering**: the law takes the NEXT available number in law-mother's sequence — not the daughter's number. If the daughter called it LAW 32 and law-mother is at LAW 30, it becomes LAW 30 in law-mother.

[↑ Back to Top](#table-of-contents)

---

## Channel: Psychology

**Source**: this daughter's `docs/psychology/` articles and/or `epiphany-index.md`
**Destination**: `$MOTHER_PATH/docs/psychology/`

**Process**:

1. Identify new articles: files in daughter's `docs/psychology/` not yet in law-mother

2. For each new article:
   a. Read the next available serial from `$MOTHER_PATH/docs/psychology/epiphany-index.md`
   b. Copy article to `$MOTHER_PATH/docs/psychology/[SERIAL].md`
      - Update serial number in the file if it differs from daughter's numbering
   c. Append index line to `$MOTHER_PATH/docs/psychology/epiphany-index.md`:
      ```
      SERIAL# | TITLE | KEYWORDS
      ```

3. If `AI-Evolution.md` was updated in daughter: review for new sections that should be merged into law-mother's `AI-Evolution.md` (additive merge — per LAW 28, never overwrite)

[↑ Back to Top](#table-of-contents)

---

## Step 3 — Commit Law-Mother Changes

After all channels are deposited:

```
cd $MOTHER_PATH
git status
git add [all modified files across channels]
git commit -m "repatriation([daughter name]): [channels] — [one-line summary]

- epiphany: [if applicable — what was repatriated]
- accretion: [if applicable — session arc deposited]
- law: LAW N — [if applicable — law name]
- psychology: [if applicable — article titles]

Repatriated from: [daughter project name]
Date: [DATE]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

[↑ Back to Top](#table-of-contents)

---

## Step 4 — Call Law-Mother /cascade (Mandatory Final Step)

After committing law-mother's channel deposits:

```
cd $MOTHER_PATH
/project:cascade "[daughter name] repatriation — [channels deposited]"
```

This runs law-mother's full 9-step cascade:
- Constitutional integrity check
- Consistency scan (propagates new law counts if a law was repatriated)
- Root doc propagation
- Accretion (law-mother's own accretion, distinct from the repatriated daughter stratum)
- Final commit

**This step is not optional.** Repatriation without cascade leaves law-mother in a partially-updated state. The deposit is made. The propagation has not run. That is drift.

The repatriation is not complete until law-mother's cascade completes.

[↑ Back to Top](#table-of-contents)

---

## Queue Write Path (When Law-Mother Unreachable)

If Step 1 cannot reach law-mother (path does not exist, law-mother repo not cloned, or inaccessible environment), do not abort silently. Queue the discovery instead.

**Check for existing queue file**:
```bash
ls .claude/REPATRIATION-QUEUE.md 2>/dev/null || echo "Queue file does not exist — will create"
```

**Determine next queue number**:
```bash
grep -c "^### QUEUE-" .claude/REPATRIATION-QUEUE.md 2>/dev/null || echo "0"
```
Next number = count + 1, zero-padded to 3 digits (e.g. QUEUE-001, QUEUE-002).

**Write queue entry**:

```markdown
### QUEUE-NNN — YYYY-MM-DD — [channel]

**Channel**: epiphany | accretion | law | psychology
**Status**: PENDING
**Queued**: YYYY-MM-DD
**Destination**: law-mother [target file — e.g. .claude/EPIPHANIES.md]
**Summary**: one-line description of what this discovery is

**Content**:
[full inline content — verbatim, self-contained per LAW 26]
[a future reader must be able to drain this entry to law-mother]
[without returning to the daughter session that produced it]
```

Append to `.claude/REPATRIATION-QUEUE.md`. If the file does not exist, create it with this header:

```markdown
# REPATRIATION-QUEUE — [project name]

Async queue for constitutional repatriation to law-mother when law-mother is unreachable.
Drain this queue by running `/project:repatriation` in a session where law-mother is accessible.
Entries with Status: PENDING are undrained. Entries with Status: DRAINED are historical record.
Do NOT delete entries — they are the lineage history (LAW 28).

**Mother**: [mother_name from LAW-LINEAGE.md]

---

## Entries
```

**After writing the queue entry**:
- Confirm the entry number and channel to the user
- Remind: run `/project:repatriation` in a session where `[mother_name]` is accessible to drain this queue
- `/ladder` Rung 11 will also surface PENDING entries at every session start

**Entry lifecycle**:
- `PENDING` → discovery waiting to be deposited in law-mother
- `DRAINED` → successfully deposited; date recorded. Never deleted (LAW 28 — prior form is data).

[↑ Back to Top](#table-of-contents)

---

## Channel Reference

| Channel | Trigger | Source | Destination | Key rule |
|---------|---------|--------|-------------|----------|
| `epiphany` | New named concept or recognition moment | daughter EPIPHANIES.md | law-mother EPIPHANIES.md | Retain daughter project name for lineage |
| `accretion` | Meaningful session (not routine maintenance) | daughter accretion.md | law-mother accretion.md | Full story — self-contained, per LAW 26 |
| `law` | New universal law in daughter | daughter PROJECT_LAWS.md + .init | law-mother PROJECT_LAWS.md + full constitutional chain | Universal only — domain-specific laws stay in daughter |
| `psychology` | New AI behavior article or evolution insight | daughter docs/psychology/ | law-mother docs/psychology/ | Serial renumbered to law-mother sequence |

**All channels** → law-mother `/cascade` (Step 4, mandatory)

**If law-mother unreachable** → Queue Write Path (entries drained in a future session)

**The repatriation is the transmission. The transmission is the law.**

[↑ Back to Top](#table-of-contents)
