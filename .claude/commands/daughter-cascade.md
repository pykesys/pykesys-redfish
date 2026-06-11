# /daughter-cascade — Daughter Project Cascade Completion

Walks the full cascade chain for a **daughter project** (lightweight reference or full adoption).
Lighter than law-mother's `/cascade` — scoped to daughter obligations.
Ends with repatriation trigger detection. If any channel is flagged, calls `/repatriation`.

Argument: `$ARGUMENTS` — optional description of what changed. If omitted, derive from git diff.

---

## Table of Contents

- [What This Command Does](#what-this-command-does)
- [Step 1 — Identify Adoption Model](#step-1--identify-adoption-model)
- [Step 2 — Identify What Changed](#step-2--identify-what-changed)
- [Step 3 — Constitutional Integrity (Full Adoption Only)](#step-3--constitutional-integrity-full-adoption-only)
- [Step 4 — Consistency Scan](#step-4--consistency-scan)
- [Step 5 — Daughter Root Doc Propagation](#step-5--daughter-root-doc-propagation)
- [Step 6 — Repatriation Trigger Detection](#step-6--repatriation-trigger-detection)
- [Step 7 — Daughter Accretion (Mandatory)](#step-7--daughter-accretion-mandatory)
- [Step 8 — Commit Daughter](#step-8--commit-daughter)
- [Step 9 — Repatriation (If Triggered)](#step-9--repatriation-if-triggered)
- [Daughter Cascade Chain Reference](#daughter-cascade-chain-reference)

---

## What This Command Does

You are executing the cascade completion protocol for a **daughter project** in the constitutional lineage.

Two models exist. Your obligations differ by model:
- **Lightweight (reference)**: no local init units, no CONSTITUTION-VERSION — inherits by pointer
- **Full adoption (fork)**: owns its own laws, init units, enforcement — full constitutional machinery

Walk every step. Do not stop between steps. Report findings inline.

[↑ Back to Top](#table-of-contents)

---

## Step 1 — Identify Adoption Model

Read the lineage declaration from `.claude/LAW-LINEAGE.md`:
```bash
cat .claude/LAW-LINEAGE.md 2>/dev/null || echo "LAW-LINEAGE.md missing — fall back to CLAUDE.md"
```

Extract key fields:
```bash
ROLE=$(grep "^role:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
MOTHER_PATH=$(grep "^mother_path:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
MOTHER_NAME=$(grep "^mother_name:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
ADOPTION_MODEL=$(grep "^adoption_model:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
```

Fallback (if LAW-LINEAGE.md absent):
```bash
grep "Law-mother:" CLAUDE.md
ls .claude/.init/law.* 2>/dev/null | wc -l
ls .claude/bin/law-manage.py 2>/dev/null
```

**Lightweight**: `adoption_model: lightweight` OR (lineage in CLAUDE.md, no local `.init/law.*`, no `law-manage.py`)
**Full adoption**: `adoption_model: full` OR (lineage in CLAUDE.md, local `.init/` directory populated, `law-manage.py` present)

Record which model. Step 3 applies only to full adoption.

[↑ Back to Top](#table-of-contents)

---

## Step 2 — Identify What Changed

```
git diff HEAD --name-only
git diff --staged --name-only
```

Classify into repatriation channels (carry forward to Step 6):
- **Epiphany**: new insight, named concept, recognition moment added to EPIPHANIES.md or session notes
- **Accretion**: session stratum deposited (always true if session was meaningful)
- **Law**: new law added to PROJECT_LAWS.md (full adoption only)
- **Psychology**: new article in docs/psychology/ or new AI behavior observation

Also classify for daughter propagation:
- **Root doc change**: CLAUDE.md, MEMORY.md, SESSION_CONTEXT.md, README.md
- **Operational change**: scripts, configs, tooling docs

[↑ Back to Top](#table-of-contents)

---

## Step 3 — Constitutional Integrity (Full Adoption Only)

Skip this step if lightweight reference model.

Run:
```
python3 .claude/bin/law-manage.py validate
```

If violation: run `python3 .claude/bin/law-manage.py regenerate` then validate again.

Check init unit coverage:
```
grep -o "^### LAW [0-9]*" .claude/PROJECT_LAWS.md | awk '{print $3}' | while read n; do
  [ ! -f ".claude/.init/law.$n" ] && echo "MISSING: .claude/.init/law.$n"
done
```

If any `.init` unit missing: create it now. Declaration and enforcement are simultaneous (LAW 26, Obligation 2).

[↑ Back to Top](#table-of-contents)

---

## Step 4 — Consistency Scan

Scan daughter docs for stale references. Key things to check:
- Project-specific version numbers, counts, or state claims that are now stale
- References to law-mother law counts (should match current law-mother state)
- Tool names, script paths, or command names that changed this session

```
grep -rn "LAW 0-[0-9]*\|[0-9]* laws\b" --include="*.md" --exclude-dir=".git" \
  | grep -v "^docs/prompts.md:\|^CHANGELOG.md:\|^\.claude/log/"
```

For each hit: historical (per LAW 28 — leave it) or current-state claim (fix it).

[↑ Back to Top](#table-of-contents)

---

## Step 5 — Daughter Root Doc Propagation

Walk your project's cascade chain (defined in your CLAUDE.md).

Verify each downstream node reflects the same state as its source. Common daughter chains:

| Source changed | Must also update |
|---------------|-----------------|
| Primary config/script | Docs that describe it |
| CLAUDE.md | SESSION_CONTEXT.md (if boot sequence changed) |
| MEMORY.md | SESSION_CONTEXT.md (if architecture facts changed) |
| Any tool | README.md or docs that reference it |
| Knowledge Base (KB) | KB index file |

Check your CLAUDE.md cascade chain definition and confirm every node is current.

[↑ Back to Top](#table-of-contents)

---

## Step 6 — Repatriation Trigger Detection

Evaluate each channel. Flag if the criterion is met:

| Channel | Criterion | Flag? |
|---------|-----------|-------|
| **Epiphany** | New named concept, pattern, or recognition moment discovered this session | yes/no |
| **Accretion** | Session was meaningful (new understanding, not just routine maintenance) | yes/no |
| **Law** | New law added to daughter's PROJECT_LAWS.md that applies universally | yes/no |
| **Psychology** | New AI behavior observation, named failure mode, or correction pattern | yes/no |

If **any channel flagged**: record the flags. Repatriation runs in Step 9.

If **no channels flagged**: skip Step 9. Routine maintenance does not require repatriation.

[↑ Back to Top](#table-of-contents)

---

## Step 7 — Daughter Accretion (Mandatory)

Deposit a stratum in this project's accretion log (typically `docs/accretion.md`).
This is the final seal for the daughter. It cannot be skipped.

Format:
```markdown
### [DATE] — [SESSION DESCRIPTION]

**Deposited**:
- [file created/changed] — [what it now contains]

**Discovered**:
- [the inflection point — what is understood now that wasn't before]

**Repatriation**: [channels flagged] / none
```

Insert at the top of the Strata section (most recent first).

[↑ Back to Top](#table-of-contents)

---

## Step 8 — Commit Daughter

```
python3 .claude/bin/law-manage.py validate   # full adoption only
git status
git add [relevant files]
git commit -m "[type]: [what changed and why]"
```

Confirm:
- [ ] Daughter consistency scan clean
- [ ] All daughter cascade nodes updated
- [ ] Daughter accretion stratum deposited
- [ ] Commit message clear

[↑ Back to Top](#table-of-contents)

---

## Step 9 — Repatriation (If Triggered)

If Step 6 flagged any channels, run repatriation now — after the daughter is committed.

**Pre-check: REPATRIATION-QUEUE.md**

Before running `/repatriation`, check for PENDING entries from prior sessions:
```bash
grep "Status: PENDING" .claude/REPATRIATION-QUEUE.md 2>/dev/null
```

If PENDING entries exist:
- List them: entry number, channel, date, summary
- Include those channels in the `/repatriation` call below (they will drain alongside new content)
- If law-mother is not accessible: new channels will also be queued (not lost)

```
/project:repatriation [channel list — include both new and queued channels]
```

Examples:
```
/project:repatriation epiphany accretion
/project:repatriation law
/project:repatriation psychology accretion
/project:repatriation epiphany law psychology accretion
```

`/repatriation` will:
1. Find law-mother via `.claude/LAW-LINEAGE.md` (`mother_path`)
2. Route each channel to the correct destination in law-mother
3. Drain any PENDING queue entries that match the channels (mark DRAINED)
4. Call `/cascade` in law-mother as its final step
5. Commit law-mother

**If law-mother is inaccessible**: `/repatriation` will write to the queue instead of depositing directly. The daughter cascade is complete — the discovery is captured. Drain in a future session.

**The daughter cascade is not complete until repatriation deposits its channels in law-mother (or queues them for a future session).**

[↑ Back to Top](#table-of-contents)

---

## Daughter Cascade Chain Reference

```
Lightweight daughter — any change:
  [changed file]
    → downstream docs in daughter's cascade chain
    → docs/accretion.md                   (MANDATORY)
    → commit daughter
    → /repatriation [channels]            (if triggered)
        → law-mother receives channels
        → law-mother /cascade runs
        → law-mother committed

Full adoption daughter — law added:
  PROJECT_LAWS.md
    → .claude/.init/law.N                 (simultaneous — LAW 26)
    → CONSTITUTION-VERSION.md             (law-manage regenerate)
    → CODEX.md                            (new entry)
    → downstream docs in daughter's chain
    → docs/accretion.md                   (MANDATORY)
    → commit daughter
    → /repatriation law [+ other channels] (if law warrants canonization)
        → law-mother PROJECT_LAWS.md receives law
        → law-mother /cascade runs
        → law-mother committed
```

**The vine repatriates. The vine grows.**

[↑ Back to Top](#table-of-contents)
