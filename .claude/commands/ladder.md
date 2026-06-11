# /ladder — Session Coherence Ladder

Verifies that the ground is solid before any new work begins.
Run at session start, after `git-audit.sh`, before the STATE BRIEFING.

**The three-part session bracket:**
```
/ladder   → verify coherence (what is currently true)    ← this command
build     → do the work
/cascade  → propagate changes (what must follow)
```

No arguments required. Runs all 11 rungs automatically.
Auto-fixes what it can. Flags what requires human judgment.
Delivers a State Report. FAIL items are blockers.

---

## Table of Contents

- [What This Command Does](#what-this-command-does)
- [Rung 1 — Navigation Scaffold](#rung-1--navigation-scaffold)
- [Rung 2 — Init Unit Completeness](#rung-2--init-unit-completeness)
- [Rung 3 — Cascade Chain Consistency](#rung-3--cascade-chain-consistency)
- [Rung 4 — Accretion Log Presence](#rung-4--accretion-log-presence)
- [Rung 5 — Memory Residency](#rung-5--memory-residency)
- [Rung 6 — Dead Reference Scan](#rung-6--dead-reference-scan)
- [Rung 7 — TOC Sync](#rung-7--toc-sync)
- [Rung 8 — Constitutional Integrity](#rung-8--constitutional-integrity)
- [Rung 9 — Orphaned Init Unit Scan](#rung-9--orphaned-init-unit-scan)
- [Rung 10 — Stale Metadata Scan](#rung-10--stale-metadata-scan)
- [Rung 11 — Repatriation Gap Detection](#rung-11--repatriation-gap-detection)
- [State Report Format](#state-report-format)
- [Write Artifact](#write-artifact)
- [Enforcement Rules](#enforcement-rules)

---

## What This Command Does

Between sessions, entropy accumulates silently. Stale metadata, missing TOC entries, broken references, orphaned `.init` units, accretion gaps, unpatriated discoveries — none of these announce themselves. The ladder is the counter-force.

Run every rung in order. Auto-fix what is auto-fixable. Flag what requires human judgment. Deliver the State Report. **Do not begin new work until all FAIL items are resolved.**

PASS and FIXED rungs are noise. FAIL rungs are blockers.

[↑ Back to Top](#table-of-contents)

---

## Rung 1 — Navigation Scaffold

**Checks**: Every `*.md` file exceeding 150 lines.
1. Table of Contents present at top — if missing, generate from actual headers and insert.
2. Back-to-Top anchor links after each major section — if missing, insert. Format: `[↑ Back to Top](#table-of-contents)`

**Auto-fixable**: Yes. Insert and report count.

```bash
# Find long .md files missing TOC
find . -name "*.md" -not -path "./.git/*" | while read f; do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 150 ]; then
    grep -q "## Table of Contents\|# Table of Contents" "$f" || echo "MISSING TOC: $f ($lines lines)"
    grep -q "↑ Back to Top" "$f" || echo "MISSING BTT: $f"
  fi
done
```

**Count assertion**: State the total count of `.md` files scanned and how many were over 150 lines. The count must come from the scan output.
> "Scanned N .md files; M over 150 lines; K required fixes."

**Report**: `PASS (N scanned, M over 150, 0 fixes needed)` / `FIXED (K files)` / `FAIL (list files)`

[↑ Back to Top](#table-of-contents)

---

## Rung 2 — Init Unit Completeness

**Checks**: Every law declared in `PROJECT_LAWS.md` has a `.claude/.init/law.N` file.

```bash
# Extract declared law numbers
grep -o "^### LAW [0-9]*" .claude/PROJECT_LAWS.md | awk '{print $3}' | while read n; do
  [ ! -f ".claude/.init/law.$n" ] && echo "MISSING .init: law.$n"
done
```

Also check META-LAWs:
```bash
grep -o "^### META-LAW [0-9]*" .claude/PROJECT_LAWS.md | awk '{print $3}' | while read n; do
  [ ! -f ".claude/.init/meta-law.$n" ] && echo "MISSING .init: meta-law.$n"
done
```

**Forced-retrieval assertion**: After running the checks above, state the exact counts found:
> "Found N .init/law.* files and M .init/meta-law.* files."

The count must come from the actual directory scan — not estimated or recalled. If you cannot produce exact counts from a live read, mark this rung FAIL.

```bash
ls .claude/.init/law.* 2>/dev/null | wc -l
ls .claude/.init/meta-law.* 2>/dev/null | wc -l
```

**Auto-fixable**: Stub creation only — content requires law knowledge. Create stub, flag for completion.

**Skip if**: Lightweight reference daughter (no local `.init/` directory — inherits from law-mother).

**Report**: `PASS (N law units, M meta-law units)` / `FIXED (n stubs created)` / `FAIL (list missing units)`

[↑ Back to Top](#table-of-contents)

---

## Rung 3 — Cascade Chain Consistency

**Checks**: Read the cascade chain from `CLAUDE.md`. For each file named in the chain:
1. Does the file exist?
2. Do tool names, script paths, and law references match across all nodes?

```bash
# Extract cascade chain files from CLAUDE.md
grep -A 30 "Cascade Chain\|cascade chain\|CASCADE" CLAUDE.md | grep "→\|bin/\|docs/\|\.md" | head -30
```

For each file in the chain: read it, check that references to other chain files use consistent names and paths.

**Forced-retrieval assertion**: After reading the cascade chain, quote the first node verbatim from `CLAUDE.md`. This value must come from reading the file — not recalled from prior context.
> "First cascade node: [exact quoted text from CLAUDE.md]"

**Auto-fixable**: No. Flag discrepancies with both values (what file A says vs what file B says). Human decides which is authoritative.

**Report**: `PASS (first node: "[quoted]")` / `FAIL (n discrepancies — list them)`

[↑ Back to Top](#table-of-contents)

---

## Rung 4 — Accretion Log Presence

**Checks**:
1. `docs/accretion.md` exists. If not: create with standard header.
2. Date of most recent stratum.
3. Compare against `git log --oneline -10` — if meaningful commits are newer than last stratum, flag the gap.

```bash
# Last accretion date
grep "^### [0-9][0-9][0-9][0-9]-" docs/accretion.md | head -1

# Recent commits
git log --oneline -5
```

**Auto-fixable**: File creation only. Gap flagging is informational — prompts you to deposit before proceeding.

**Forced-retrieval assertion**: Quote the date of the most recent stratum header from `docs/accretion.md`. Must be read from the file — not recalled.
> "Last stratum: [YYYY-MM-DD — exact title]"

**Report**: `PASS (last stratum: YYYY-MM-DD)` / `FAIL (last stratum: DATE — n commits since then)`

[↑ Back to Top](#table-of-contents)

---

## Rung 5 — Memory Residency

**Checks**: Varies by adoption model.

**Step 1 — Determine adoption model**:
```bash
cat .claude/LAW-LINEAGE.md 2>/dev/null || grep "Law-mother:" CLAUDE.md 2>/dev/null
ls .claude/.init/law.* 2>/dev/null | wc -l
```
- `role: mother` in LAW-LINEAGE.md → **law-mother**
- `role: daughter` + `adoption_model: lightweight` → **lightweight reference**
- `role: daughter` + `adoption_model: full` → **full adoption**
- Fallback (LAW-LINEAGE.md absent): lineage declaration present + no local `.init/law.*` = **lightweight reference**; lineage declaration present + local `.init/` populated = **full adoption**; no lineage declaration = **law-mother itself**

**Step 2 — Apply model-appropriate check**:

*Law-mother*:
- Verify `MEMORY.md` exists at repo root and is not a pointer file.
- External auto-memory (`.claude/projects/<hash>/memory/`) may exist but should not contain project architectural facts — those belong in `MEMORY.md`.

*Full adoption daughter*:
- Verify `MEMORY.md` exists at repo root.
- External auto-memory is a **leak** — flag any project-specific content found there.
- Project memory must be version-controlled and portable.

*Lightweight reference daughter*:
- Verify `MEMORY.md` exists at repo root.
- External auto-memory is **sanctioned** — lightweight daughters may use both `MEMORY.md` (project facts) and external auto-memory (session continuity). Both are valid channels.
- Flag only if `MEMORY.md` is missing entirely.

**Auto-fixable**: File creation only. Memory migration requires human confirmation.

**Forced-retrieval assertion**: When MEMORY.md is present, read it and quote the exact text of the most recent entry under `Last significant change` (or equivalent — the last session summary line). Quote verbatim. If you cannot produce a verbatim quote because you did not read the file, mark this rung FAIL.

> "Last significant change: [exact quoted text]"

**Report**: `PASS (Last change: [quoted date+summary])` / `FAIL (detail)`

[↑ Back to Top](#table-of-contents)

---

## Rung 6 — Dead Reference Scan

**Checks**: All `*.md` files for broken links.
- `[text](relative/path.md)` — target file exists?
- `[text](#anchor)` — anchor exists in same file?
- Bare path references to `bin/`, `docs/`, `.claude/` — path resolves?

```bash
# Find broken file references (not anchors)
grep -rn "\[.*\](\./\|\.\./" --include="*.md" | grep -v "http" \
  | sed "s/.*(\(.*\))/\1/" | while read path; do
    [ ! -f "$path" ] && echo "BROKEN: $path"
  done
```

**Auto-fixable**: No. Broken links may be deleted files (update reference) or renames (update path). Flag for human resolution.

**Count assertion**: State the total count of `.md` files scanned for broken references.
> "Scanned N .md files for broken references."

**Report**: `PASS (N files scanned, 0 broken)` / `FAIL (n broken — list them)`

[↑ Back to Top](#table-of-contents)

---

## Rung 7 — TOC Sync

**Checks**: Each `*.md` with a Table of Contents:
1. Every TOC entry `[text](#anchor)` has a matching header in the file body.
2. Every major `##` or `###` header has a TOC entry.

```bash
# For each .md with a TOC, extract TOC anchors vs actual headers
for f in $(grep -rl "## Table of Contents\|# Table of Contents" --include="*.md"); do
  echo "=== $f ==="
  echo "TOC anchors:"
  grep -o "(#[^)]*)" "$f" | tr -d '()' | sort
  echo "Headers:"
  grep "^## \|^### " "$f" | sed 's/[^a-zA-Z0-9 -]//g' | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | sort
done
```

**Auto-fixable**: Yes for adding missing TOC entries from headers. Flag orphaned TOC entries (may point to deleted sections).

**Count assertion**: State the count of `.md` files that contain a Table of Contents section.
> "Found N files with TOC sections."

**Report**: `PASS (N files with TOC, 0 issues)` / `FIXED (n entries added)` / `FAIL (n orphaned TOC entries)`

[↑ Back to Top](#table-of-contents)

---

## Rung 8 — Constitutional Integrity

**Checks**: Depends on adoption model (from Rung 5).

*Law-mother*:
```bash
python3 .claude/bin/law-manage.py validate
```
Any output beyond "All invariants satisfied" is a FAIL.

**Forced-retrieval assertion**: Quote the exact law count line from the validate output — e.g. `"✓ session-loader.sh : 30 laws (LAW 0-29)"`. Do not summarize as "passed" without stating the count. If you ran validate and cannot quote the count line, mark this rung FAIL.

*Full adoption daughter*:
- Count `### LAW` entries in `PROJECT_LAWS.md` TOC.
- Compare to count in `CONSTITUTION-VERSION.md`.
- Mismatch = FAIL.

*Lightweight reference daughter*:
- Verify lineage declaration points to a reachable law-mother.
- Verify law-mother's `law-manage.py validate` passes (if accessible).
- No local constitutional database to validate.

**Auto-fixable**: `law-manage.py regenerate` fixes derived files in law-mother and full adoption. Count mismatches require manual `CONSTITUTION-VERSION.md` update.

**Report**: `PASS` / `FIXED (regenerated)` / `FAIL (violation detail)`

[↑ Back to Top](#table-of-contents)

---

## Rung 9 — Orphaned Init Unit Scan

**Checks**: Every `.claude/.init/law.N` has a declared `LAW N` in `PROJECT_LAWS.md`.

```bash
for f in .claude/.init/law.*; do
  n=$(echo "$f" | grep -o "[0-9]*$")
  grep -q "^### LAW $n" .claude/PROJECT_LAWS.md || echo "ORPHANED: $f (no LAW $n declared)"
done
```

**Auto-fixable**: No. Orphan may be a deleted law (remove unit) or accidentally removed declaration (restore it). Human judgment required.

**Skip if**: Lightweight reference daughter (no local `.init/`).

**Count assertion**: State the total count of `.init/law.*` and `.init/meta-law.*` files checked.
> "Checked N .init/law.* and M .init/meta-law.* files against PROJECT_LAWS.md."

**Report**: `PASS (N law units checked, 0 orphans)` / `FAIL (n orphans — list them)` / `SKIP (lightweight)`

[↑ Back to Top](#table-of-contents)

---

## Rung 10 — Stale Metadata Scan

**Checks**: Files declaring `Last Updated:` or `**Last Updated**` dates.

```bash
# Find files with Last Updated declarations
grep -rn "Last Updated\|last updated" --include="*.md" | grep -v ".git" | while IFS=: read file line content; do
  declared=$(echo "$content" | grep -o "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]" | head -1)
  if [ -n "$declared" ]; then
    git_date=$(git log --follow -1 --format="%ai" -- "$file" 2>/dev/null | cut -d' ' -f1)
    if [ -n "$git_date" ] && [ "$git_date" \> "$declared" ]; then
      echo "STALE: $file (declares $declared, last commit $git_date)"
    fi
  fi
done
```

**Auto-fixable**: Date updates where the change is clear. Flag version bumps for human judgment.

**Count assertion**: State the count of files found with `Last Updated` declarations.
> "Found N files with Last Updated declarations."

**Report**: `PASS (N files checked, 0 stale)` / `FIXED (n dates updated)` / `FAIL (n stale — list them)`

[↑ Back to Top](#table-of-contents)

---

## Rung 11 — Repatriation Gap Detection

**Checks**: For daughter projects — does this session have unpatriated discoveries that should have traveled to law-mother?

**Step 1 — Determine if this is a daughter project**:
```bash
cat .claude/LAW-LINEAGE.md 2>/dev/null
```
Read `role` field:
- `role: mother` → this is law-mother. Skip this rung. Mark SKIP.
- `role: daughter` → extract `mother_path` and `mother_name` and proceed.
- File missing → fall back: `grep "Law-mother:" CLAUDE.md 2>/dev/null`. If no lineage found → SKIP.

```bash
ROLE=$(grep "^role:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
MOTHER_PATH=$(grep "^mother_path:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
MOTHER_NAME=$(grep "^mother_name:" .claude/LAW-LINEAGE.md 2>/dev/null | awk '{print $2}')
```

**Step 2 — Check REPATRIATION-QUEUE.md for PENDING entries**:
```bash
grep -c "Status: PENDING" .claude/REPATRIATION-QUEUE.md 2>/dev/null || echo "0"
```

If any PENDING entries found:
1. List each PENDING entry by number, channel, date, and summary line
2. Report: `PENDING QUEUE: N entries awaiting drain to $MOTHER_NAME`
3. Print reminder: "Run `/project:repatriation` in a session where `$MOTHER_NAME` is accessible to drain these entries."
4. These are not new gaps — they are queued. Do not double-count with Step 3.

**Step 3 — Check repatriation channels for gaps** (daughter only, law-mother accessible):

Skip this step if law-mother is not accessible (`ls "$MOTHER_PATH/.claude/PROJECT_LAWS.md"` fails).

*Epiphany channel*: Compare most recent session arc date in daughter's `EPIPHANIES.md` vs most recent epiphany repatriated to law-mother bearing this project's name.
```bash
grep -m1 "^### Session\|^### .*$(basename $PWD)" $MOTHER_PATH/.claude/EPIPHANIES.md
grep -m1 "^### Session\|^## Session" .claude/EPIPHANIES.md
```

*Accretion channel*: Compare most recent stratum date in daughter's `docs/accretion.md` vs most recent stratum in law-mother bearing this project's name.

*Psychology channel*: List `docs/psychology/*.md` articles in daughter. Check which serial numbers are present in `$MOTHER_PATH/docs/psychology/epiphany-index.md`.

*Law channel*: List laws in daughter's `PROJECT_LAWS.md` that are marked universal or have no domain tag. Check which exist in law-mother.

**Step 4 — Report gaps**:
```
Repatriation gaps found:
  epiphany: last arc 2026-04-10 — not found in law-mother
  psychology: articles 000007, 000008 not in law-mother index
  law: none detected
→ Run: /project:repatriation epiphany psychology
```

If PENDING queue entries exist AND new gaps found: report both. Queue entries are not gaps — they are already captured. New gaps are undiscovered.

**Forced-retrieval assertion** (daughter projects only): Quote the date and title of the most recent session arc from this project's `.claude/EPIPHANIES.md`. Must be read from the file.
> "Last session arc: [YYYY-MM-DD — exact title from EPIPHANIES.md]"

**Auto-fixable**: No — flag only. Repatriation requires `/project:repatriation` with appropriate channels.

**Report**: `PASS (no gaps — last arc: YYYY-MM-DD)` / `FAIL (gaps — list channels and suggested /repatriation command)` / `SKIP (law-mother)`

If PENDING queue entries exist, append to report: `PENDING QUEUE: N entries — drain with /project:repatriation when $MOTHER_NAME accessible`

[↑ Back to Top](#table-of-contents)

---

## State Report Format

Deliver this before any new work begins:

```
⚖️  Session Coherence Ladder — State Report
============================================
Rung 1:  Navigation Scaffold          [PASS (N scanned, M over 150) | FIXED (K files) | FAIL]
Rung 2:  Init Unit Completeness       [PASS (N law units, M meta-law units) | FIXED (n stubs) | FAIL | SKIP (lightweight)]
Rung 3:  Cascade Chain Consistency    [PASS (first node: "...") | FAIL (n discrepancies)]
Rung 4:  Accretion Log Presence       [PASS (last stratum: YYYY-MM-DD) | FAIL (last: DATE, n commits since)]
Rung 5:  Memory Residency             [PASS (Last change: DATE — summary) | FAIL (detail)]
Rung 6:  Dead References              [PASS (N files scanned, 0 broken) | FAIL (n broken)]
Rung 7:  TOC Sync                     [PASS (N files with TOC) | FIXED (n entries) | FAIL]
Rung 8:  Constitutional Integrity     [PASS (30 laws, LAW 0-29) | FIXED (regenerated) | FAIL (detail)]
Rung 9:  Orphaned Init Units          [PASS (N units checked, 0 orphans) | FAIL (n orphans) | SKIP (lightweight)]
Rung 10: Stale Metadata               [PASS (N files checked, 0 stale) | FIXED (n dates) | FAIL]
Rung 11: Repatriation Gaps            [PASS (no gaps — last arc: YYYY-MM-DD) | FAIL (channels) | SKIP (law-mother)]
============================================
Ground is solid. Ready to build.
--- OR ---
n FAIL items require resolution before new work begins.
Suggested actions: [list]
```

PASS: no action needed. Rungs 2, 3, 4, 5, 8, 11 must include quoted or counted values — "PASS" without a value is treated as FAIL on those rungs.
FIXED: auto-corrected, count reported.
FAIL: blocker — resolve before proceeding.
SKIP: rung does not apply to this adoption model.

[↑ Back to Top](#table-of-contents)

---

## Write Artifact

After delivering the State Report, write a dated entry to `SESSION_CONTEXT.md`. This is the proof-of-execution artifact — it either exists in the file or the ladder did not run. A future reader (or the next session's Claude) can verify the ladder ran by checking for this entry.

**If `SESSION_CONTEXT.md` has no `## Ladder Run Log` section**: append it at the bottom of the file before any final BTT anchor.

**Entry format**:
```markdown
### YYYY-MM-DD — Ladder Run

Rung 2: [PASS (N law units, M meta-law units) | SKIP]
Rung 3: [PASS (first node: "...") | FAIL]
Rung 4: [PASS (last stratum: YYYY-MM-DD) | FAIL]
Rung 5: [PASS (Last change: "...") | FAIL]
Rung 8: [PASS (N laws, LAW 0-N-1) | FAIL]
Rung 11: [PASS (last arc: YYYY-MM-DD) | SKIP (law-mother) | FAIL]
Full State: [PASS — ground solid | FAIL: Rung X (detail)]
```

Include only rungs with quoted values (2, 3, 4, 5, 8, 11). Scanning rungs (1, 6, 7, 9, 10) are omitted unless they FAIL. A FAIL on any rung must appear in the Full State line.

**Why this matters**: The Veil (LAW 29) can produce a convincing State Report without reading any file. The write artifact cannot be faked — it is either written to SESSION_CONTEXT.md or it is not. The next session's ladder run will verify it.

[↑ Back to Top](#table-of-contents)

---

## Enforcement Rules

```
Violation: Session starts, Claude begins building without running the ladder.
Response:  Stop. Run /ladder. Deliver State Report. Resolve all FAIL items. Then build.

Violation: A FAIL item is marked "low priority" and work proceeds.
Response:  There is no priority ordering of broken ground. All FAIL items
           are blockers. Fix or escalate to human, then proceed.

Violation: "The session is short, skip the ladder."
Response:  The ladder is not calibrated to session length. Entropy does not
           accumulate proportionally to session length. Run all 11 rungs.

Violation: Rung 11 shows repatriation gaps but /repatriation is not called.
Response:  The discovery stays in the daughter and dies with it. Run
           /project:repatriation with the flagged channels before closing.

Violation: Rungs 2, 5, or 8 show "PASS" with no quoted value.
Response:  A PASS with no quoted value is a simulation, not an execution.
           The forced-retrieval requirement exists precisely because Claude
           can produce plausible PASS text without reading any file.
           Re-run the rung, read the file, produce the quoted value.
```

[↑ Back to Top](#table-of-contents)

---

**Law**: LAW 27 — Session Coherence Ladder (PROJECT_LAWS.md § LAW 27)
**Pair**: `/cascade` — runs at session end after the build
**Chain**: `/ladder` → build → `/cascade` → commit
