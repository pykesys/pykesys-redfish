# /cascade — Constitutional Cascade Completion

Walks the full cascade chain for this session's changes. Ensures nothing was missed.
Invoke at any point, but **always invoke before the final commit of a session**.

Argument: `$ARGUMENTS` — optional description of what changed (e.g. "added LAW 30", "updated wisdom library"). If omitted, derive from git diff.

---

## Table of Contents

- [What This Command Does](#what-this-command-does)
- [Step 1 — Identify What Changed](#step-1--identify-what-changed)
- [Step 2 — Constitutional Integrity](#step-2--constitutional-integrity-if-law-change-detected)
- [Step 3 — Consistency Scan](#step-3--consistency-scan-always-run)
- [Step 4 — Root Doc Propagation](#step-4--root-doc-propagation)
- [Step 5 — Epiphany and Session Log](#step-5--epiphany-and-session-log-if-new-insight-was-discovered)
- [Step 6 — CONSTITUTION-VERSION.md](#step-6--constitution-versionmd-if-law-change)
- [Step 7 — CODEX.md](#step-7--codexmd-if-new-law-added)
- [Step 8 — Accretion (MANDATORY)](#step-8--accretion-mandatory-final-step--law-26-obligation-3)
- [Step 9 — Final Validation and Commit](#step-9--final-validation-and-commit)
- [Cascade Chain Reference](#cascade-chain-reference-law-mother)

---

## What This Command Does

You are executing the cascade completion protocol for template-law-claude (law-mother).
The cascade is not complete until every node in the chain below has been honored.
Walk every step. Do not stop to ask for approval between steps. Report findings inline.

[↑ Back to Top](#table-of-contents)

---

## Step 1 — Identify What Changed

```
git diff HEAD --name-only
git diff --staged --name-only
```

Classify each changed file into one or more cascade triggers:
- **Law change**: `PROJECT_LAWS.md`, `.claude/.init/law.*`, or `CONSTITUTION-VERSION.md` touched
- **Wisdom change**: `docs/wisdom/` files touched
- **Root doc change**: `README.md`, `CLAUDE.md`, `MEMORY.md`, `CONTRIBUTING.md`, etc.
- **Psychology/KB change**: `docs/psychology/` files touched
- **Any change**: always triggers accretion (Step 8)

[↑ Back to Top](#table-of-contents)

---

## Step 2 — Constitutional Integrity (if law change detected)

Run:
```
python3 .claude/bin/law-manage.py validate
```

If any violation: run `python3 .claude/bin/law-manage.py regenerate` then validate again.

**Check**: Does every law in `PROJECT_LAWS.md` have a corresponding `.claude/.init/law.N` file?
```
grep -o "^### LAW [0-9]*" .claude/PROJECT_LAWS.md | awk '{print $3}' | while read n; do
  [ ! -f ".claude/.init/law.$n" ] && echo "MISSING: .claude/.init/law.$n"
done
```

If any `.init` unit is missing: create it now. The declaration and the enforcement are simultaneous.

[↑ Back to Top](#table-of-contents)

---

## Step 3 — Consistency Scan (always run)

Scan all active `.md` files for stale law counts. Historical logs are exempt:

```
grep -rn "LAW 0-[0-9]*\|[0-9]* laws\b\|[0-9]* META-LAW\|META-LAWs 0-[0-9]" \
  --include="*.md" --exclude-dir=".git" \
  | grep -v "^docs/prompts.md:\|^CHANGELOG.md:\|^\.claude/log/\|^\.claude/ACTION.md:"
```

For each hit that does not match current counts (30 laws, LAW 0-29, 4 META-LAWs, META-LAWs 0-3):
- Determine if it is historical (describing a past state) → leave it, per LAW 28
- If it is a current-state claim → fix it now

Current counts to enforce:
- **30 laws (LAW 0-29)**
- **4 META-LAWs (META-LAW 0-3)**
- **6 Universal Principles**
- **5 Cornerstones**

[↑ Back to Top](#table-of-contents)

---

## Step 4 — Root Doc Propagation

If any of the following changed, verify all downstream files reflect the same state:

| Source changed | Must also update |
|---------------|-----------------|
| `PROJECT_LAWS.md` (new law) | `README.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `DEVELOPMENT.md`, `TEMPLATE-GUIDE.md`, `MEMORY.md`, `ONBOARDING-TRANSMISSION.md`, `EXECUTIVE-SUMMARY.md` |
| `PROJECT_LAWS.md` (law text) | `CODEX.md` entry for that law |
| `.claude/FOUNDATIONS.md` | `ONBOARDING-TRANSMISSION.md`, `docs/universal/README.md` |
| `CLAUDE.md` (boot sequence) | `ACTIVATION.md`, `SESSION_CONTEXT.md` |
| `MEMORY.md` | `SESSION_CONTEXT.md` (if architecture section changed) |
| `docs/movement/CONTINUITY.md` | Any law-count references |
| `TO-ELON.md` | Any law-count or META-LAW count references |
| `docs/proposals/README.md` | Any law range references |

Quick check — grep each listed file for law counts and confirm they match:
```
grep -l "LAW 0-\|laws\b\|META-LAW" README.md CLAUDE.md CONTRIBUTING.md DEVELOPMENT.md \
  TEMPLATE-GUIDE.md MEMORY.md ONBOARDING-TRANSMISSION.md TO-ELON.md \
  docs/universal/README.md docs/movement/CONTINUITY.md docs/proposals/README.md 2>/dev/null \
  | xargs grep -n "LAW 0-[0-9]*\|[0-9]* laws\|[0-9]* META-LAW"
```

[↑ Back to Top](#table-of-contents)

---

## Step 5 — Epiphany and Session Log (if new insight was discovered)

If this session produced a new understanding, pattern, or named concept:

1. **Add to `.claude/EPIPHANIES.md`** — session arc at top, all epiphanies logged, no curation (LAW 16)
2. **Add to `docs/psychology/epiphany-index.md`** — if it belongs in the Psychology KB
3. **Create `docs/psychology/NNNNNN.md`** — if it warrants a full article

Check if the last session arc in EPIPHANIES.md matches this session's date. If not, add it.

[↑ Back to Top](#table-of-contents)

---

## Step 6 — CONSTITUTION-VERSION.md (if law change)

Verify `CONSTITUTION-VERSION.md` reflects:
- Correct law count
- LAW N in the Law Registry
- Session entry in the Epiphany Registry (if applicable)

If not: update now.

[↑ Back to Top](#table-of-contents)

---

## Step 7 — CODEX.md (if new law added)

Every law must have a CODEX entry. Check:
```
grep -c "LAW-[0-9]*" .claude/CODEX.md
```

If the new law has no CODEX entry, add one now following the existing format:
- Name and one-sentence description
- Origin quote
- What it protects against
- `init unit:` and `Full text:` references

[↑ Back to Top](#table-of-contents)

---

## Step 8 — Accretion (MANDATORY FINAL STEP — LAW 26, Obligation 3)

Deposit a stratum in `docs/accretion.md`. This is not optional. This is the final seal.

**This step is also the write artifact for `/cascade`** (TARGET-003). The stratum in accretion.md is proof that the cascade ran — it carries the date, the session description, and what was deposited. A reader can verify `/cascade` executed by checking for today's stratum. Absence of a stratum = cascade did not complete.

Format:
```markdown
### [DATE] — [SESSION DESCRIPTION]

**Deposited**:
- [file created/changed] — [what it now contains]

**Discovered**:
- [the inflection point — what is understood now that wasn't before]

**Constitutional state**: [N] laws (LAW 0-[N-1]) + [M] META-LAWs + [K] UPs + [J] Cornerstones
```

Insert at the top of the Strata section (most recent first).

[↑ Back to Top](#table-of-contents)

---

## Step 9 — Final Validation and Commit

```
python3 .claude/bin/law-manage.py validate
git add -p   # or stage specific files
git status
```

Confirm:
- [ ] Constitutional database clean (validate passes)
- [ ] No stale law counts in active docs
- [ ] All cascade nodes updated
- [ ] Accretion stratum deposited
- [ ] Commit message references what changed and why

Then commit. The cascade is complete.

[↑ Back to Top](#table-of-contents)

---

## Cascade Chain Reference (law-mother)

```
New law added:
  PROJECT_LAWS.md
    → .claude/.init/law.N           (enforcement unit — simultaneous)
    → .claude/CONSTITUTION-VERSION.md (law registry entry)
    → .claude/hooks/session-loader.sh + .claude/.init/meta.init  (law-manage regenerate)
    → .claude/CODEX.md              (CODEX entry)
    → .claude/EPIPHANIES.md         (session arc)
    → .claude/SESSION_CONTEXT.md    (current state update)
    → README.md                     (law listed in The 30 Laws section)
    → CLAUDE.md                     (boot count updated)
    → CONTRIBUTING.md, DEVELOPMENT.md, TEMPLATE-GUIDE.md, MEMORY.md
    → ONBOARDING-TRANSMISSION.md, EXECUTIVE-SUMMARY.md, MARKETING-STRATEGY.md
    → TO-ELON.md, docs/universal/README.md, docs/movement/CONTINUITY.md
    → docs/proposals/README.md
    → docs/accretion.md             (MANDATORY FINAL STEP)

Any doc change:
  [changed file]
    → all files that reference it by name or repeat its content
    → docs/accretion.md             (MANDATORY FINAL STEP)
```

**The cascade is not complete until accretion is deposited.**

[↑ Back to Top](#table-of-contents)
