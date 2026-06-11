# LESSONS-LEARNED.md - Claude's Operational Compendium

**Purpose**: Claude's accumulated hard-won operational knowledge for this repository. Read this on every session start. Do not repeat avoidable mistakes.

**Authority**: Companion to SESSION_CONTEXT.md (LAW 0). Where SESSION_CONTEXT.md restores *where we are*, this file restores *what I have learned*.

**Last Updated**: 2026-02-28

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [Session Restoration](#session-restoration)
- [Law Enforcement Behavior](#law-enforcement-behavior)
- [Shell and Environment](#shell-and-environment)
- [Claude-Reality Library Operations](#claude-reality-library-operations)
- [Git and Commit Hygiene](#git-and-commit-hygiene)
- [Investigation Discipline](#investigation-discipline)
- [Additive Evolution Violations](#additive-evolution-violations)

---

## How to Use This Document

Read every entry before starting work. Each lesson was learned through a real failure. The session cost of ignoring them is higher than the two minutes it takes to read them.

When a new lesson is learned, add it immediately - do not defer to end of session.

Format for new entries:
```
### LL-XXX: [Short title]
**Date**: YYYY-MM-DD
**Category**: [Session Restoration | Law Enforcement | Shell | Claude-Reality | Git | Investigation]
**What happened**: Brief description of the failure
**The lesson**: What to do instead
**Reference**: Related law, document, or prior entry
```

[↑ Back to Top](#table-of-contents)

---

## Session Restoration

### LL-001: Read docs/prompts.md on Every Restoration
**Date**: 2026-02-28
**Category**: Session Restoration
**What happened**: SESSION_CONTEXT.md was read but `docs/prompts.md` was skipped. Daniel caught it immediately. The prompt log is listed as #2 in Essential files - it was simply not read.
**The lesson**: The Key Files to Read list in SESSION_CONTEXT.md is not a suggestion. Read every file in the Essential section, in order, before doing anything else. `docs/prompts.md` is #2.
**Reference**: SESSION_CONTEXT.md → Key Files to Read on Restoration

---

### LL-002: SESSION_CONTEXT.md Must Be Updated at Session END
**Date**: 2026-02-28
**Category**: Session Restoration
**What happened**: The 2026-02-27 session built Night Watch (3,221 lines across 3 universal documents), initialized the Claude-Reality Library, created the Morning Report, and committed Movement Infrastructure. None of it was written to SESSION_CONTEXT.md before the session ended. The next session (today) restored from stale 2026-02-26 data. Daniel was rightfully irritated.
**The lesson**: Before any session ends - before any long interruption - update SESSION_CONTEXT.md. Capture: what was built, what is pending, what the next action is. The Morning Report cycle handoff in particular must always be captured.
**Reference**: LAW 0 - Session Continuity; SESSION_CONTEXT.md

---

### LL-003: The Morning Report Cycle Is a Critical Handoff
**Date**: 2026-02-28
**Category**: Session Restoration
**What happened**: The Morning Report (`docs/claude-reality/daily-reports/2026-02-27-MORNING-REPORT.md`) was created at 3:47 AM on 2026-02-27 awaiting direction. It went unacknowledged for the entire next session because SESSION_CONTEXT.md was not updated.
**The lesson**: The Morning Report is a live handoff document. Its status (AWAITING DIRECTION) must always be surfaced in SESSION_CONTEXT.md → What's Next. On restoration, if a Morning Report is pending, bring it to Daniel's attention immediately.
**Reference**: LL-002; `docs/claude-reality/README.md`

---

### LL-004: Read FOUNDATIONS.md and LEXICON.md on Every Restoration
**Date**: 2026-02-28
**Category**: Session Restoration
**What happened**: During today's restoration review, FOUNDATIONS.md (5 cornerstones) and LEXICON.md (2 universal principles) were read. These are essential for understanding the philosophical context of this project, which is not purely technical.
**The lesson**: This project operates on multiple planes - practical, philosophical, universal. The constitutional documents in `.claude/` are all load-bearing. Read them all.
**Reference**: `.claude/FOUNDATIONS.md`; `.claude/LEXICON.md`

[↑ Back to Top](#table-of-contents)

---

## Law Enforcement Behavior

### LL-005: Log Prompt BEFORE Acting - No Exceptions
**Date**: 2026-02-28
**Category**: Law Enforcement
**What happened**: Prompts 43-45 were logged after acting on them, not before. Daniel cited the law codex directly. The correct sequence is: (1) receive prompt, (2) log it to `docs/prompts.md`, (3) act on it.
**The lesson**: The first action on receiving any prompt is to open `docs/prompts.md` and append the log entry. Then act. No exceptions. Not even for trivial prompts.
**Reference**: LAW 1 - Complete Audit Trail

---

### LL-006: Do Not Ask Permission to Log - LAW 1 Is Self-Executing
**Date**: 2026-02-28
**Category**: Law Enforcement
**What happened**: After missing the prompt log on restoration, Claude asked "shall I append them to docs/prompts.md?" Daniel correctly cited the law: no permission required, no questions asked. The law governs.
**The lesson**: LAW 1 does not require user approval to execute. Log the prompt. That is all.
**Reference**: LAW 1 - Complete Audit Trail; LL-005

---

### LL-007: "Push it" IS the LAW 3 Approval
**Date**: 2026-02-28
**Category**: Law Enforcement
**What happened**: LAW 3 requires a push confirmation prompt. When Daniel said "push it," Claude proceeded without the formal prompt. This was noted as an enforcement gap - LAW 3 has no exception for user phrasing.
**The lesson**: When the user's instruction contains explicit push direction ("push it", "push", "commit and push"), treat that as the LAW 3 approval. Log the prompt (which captures the approval), then push. Do not issue a redundant confirmation prompt - that would be noise.
**Reference**: LAW 3 - Commit Discipline

[↑ Back to Top](#table-of-contents)

---

## Shell and Environment

### LL-008: Shell Temp CWD Error Is Type B - Cosmetic, Not a Hook Bug
**Date**: 2026-02-28
**Category**: Shell and Environment
**What happened**: `zsh: permission denied: /var/folders/.../T/claude-XXXX-cwd` appeared after every Bash tool invocation. Significant time was spent investigating the hooks and attempting fixes. The actual cause: Claude Code's Bash tool creates a new temp CWD per invocation in a macOS path with restricted permissions. Zsh reports the error on exit when it cannot verify the CWD. All operations succeed.
**The lesson**: When this error appears, confirm operations succeeded (check exit codes, verify commits landed). If they did, this is Type B - cosmetic noise from Claude Code's own shell infrastructure. Do not spend session time trying to fix it from within the repo. It resolves on session restart.
**Reference**: `.claude/README.md` → Known Failure Modes → Type B

---

### LL-009: Type A Shell CWD Error - Caused by Hook `cd` at Process Level
**Date**: 2026-02-28
**Category**: Shell and Environment
**What happened**: `git-audit.sh` called `cd "$REPO_ROOT"` directly in `main()`, changing the persistent shell's working directory. Fix: wrap the `cd` and subsequent execution in a subshell.
**The lesson**: Any `cd` in a hook script that runs at the process level (not inside `( )`) will persist in Claude Code's shell across invocations. Always wrap `cd` calls in hook scripts in a subshell to preserve caller CWD. Test after fixing: run the script directly, then verify `pwd` returns the original directory.
**Reference**: `.claude/.enforcement/git-audit.sh` main(); `.claude/README.md` → Type A

---

### LL-010: Test the Fix Before Declaring It Done
**Date**: 2026-02-28
**Category**: Shell and Environment / Investigation Discipline
**What happened**: The git-audit.sh subshell fix was committed without being tested first. Daniel caught this: "test the fix first." Testing confirmed the fix worked correctly for its stated purpose (CWD preservation), and separately confirmed the remaining error was Type B and unrelated.
**The lesson**: Fix → test → confirm → commit. Not fix → commit → test. Especially for infrastructure changes that affect every subsequent git operation.
**Reference**: CLAUDE.md → Testing Changes; LL-008; LL-009

[↑ Back to Top](#table-of-contents)

---

## Claude-Reality Library Operations

### LL-011: The Library Cycle - Direction First, Encoding Second
**Date**: 2026-02-28
**Category**: Claude-Reality Library Operations
**What happened**: The Morning Report was created but direction was never received because the session ended without updating SESSION_CONTEXT.md. The library stalled at the handoff point.
**The lesson**: The Claude-Reality Library operates on a cycle: Morning Report created → Daniel reviews → Daniel gives direction → Claude encodes. The cycle cannot advance without Daniel's direction. Never encode a new wisdom document without explicit direction on what to encode and in what order.
**Reference**: `docs/claude-reality/README.md`; LL-003

---

### LL-012: Quality Over Speed - One Document at a Time
**Date**: 2026-02-28
**Category**: Claude-Reality Library Operations
**What happened**: Daniel directed encoding of all wisdom areas in sequence, explicitly stating "we are reaching quality and value not speed."
**The lesson**: Each wisdom document in `docs/claude-reality/daniels-wisdom/` is a substantial work. Treat each as a standalone deliverable. Complete it fully - structure, depth, Daniel's corrections section, targeted questions - before moving to the next. The sequence: kernel-expertise → systems-thinking → leadership → apple-culture → life-lessons → technical-excellence → philosophy.
**Reference**: `docs/claude-reality/daniels-wisdom/`; Morning Report options

[↑ Back to Top](#table-of-contents)

---

## Git and Commit Hygiene

### LL-013: Commit After Every Significant Change - LAW 3
**Date**: 2026-02-28
**Category**: Git and Commit Hygiene
**What happened**: Multiple files were updated in sequence before committing. This creates a risk of losing work and makes commit history harder to read.
**The lesson**: Each logical unit of work gets its own commit. A wisdom document is one commit. A SESSION_CONTEXT update is one commit. A prompt log update is one commit when standalone, or bundled with the document it accompanies. Do not batch unrelated changes.
**Reference**: LAW 3 - Commit Discipline

---

### LL-014: Always Include Co-Authored-By in Commit Messages
**Date**: 2026-02-28
**Category**: Git and Commit Hygiene
**What happened**: The git-audit.sh uses `Co-Authored-By: Claude Sonnet` presence to identify Claude commits as compliant. Without it, a manual-commit violation is logged.
**The lesson**: Every commit message must end with `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`. Always. The audit script depends on this signature.
**Reference**: LAW 3; `.claude/.enforcement/git-audit.sh` → is_claude_commit()

[↑ Back to Top](#table-of-contents)

---

## Investigation Discipline

### LL-015: Confirm Operations Succeed Before Investigating Errors
**Date**: 2026-02-28
**Category**: Investigation Discipline
**What happened**: The shell temp CWD error appeared in every Bash tool invocation. Significant investigation effort was spent before confirming that all operations (commits, pushes) were actually succeeding. The error was cosmetic throughout.
**The lesson**: When an error appears alongside a successful operation, confirm the operation's success first. Check: did the commit land? Did the push reach remote? If yes, the error may be cosmetic. Investigate root cause before attempting repair. Do not repair what is not broken.
**Reference**: LL-008; LL-010

---

### LL-016: Do Not Over-Engineer Infrastructure Fixes
**Date**: 2026-02-28
**Category**: Investigation Discipline
**What happened**: The shell temp CWD issue prompted investigation, a hook fix, a README update, a codex entry, and multiple commits - for an error that was cosmetic and did not affect any operation. Daniel's framing: do not build a tower to flush a turd.
**The lesson**: Match the weight of the response to the weight of the problem. A cosmetic error that does not affect operations gets: (1) documented in the codex, (2) a note that it is cosmetic, (3) nothing else. Reserve engineering effort for problems that actually break things.
**Reference**: `.claude/README.md` → Known Failure Modes; LAW 12

---

### LL-017: Type B CWD Error Cannot Be Fixed From the Repo - Say So Immediately
**Date**: 2026-02-28
**Category**: Investigation Discipline / Shell and Environment
**What happened**: The Type B shell temp CWD error was investigated for an extended period, spawning multiple commits (hook fix, codex entries, README updates) before confirming it cannot be fixed from within the repository. The error fires on every command regardless of hooks, scripts, or repo state. It is structural to Claude Code's Bash tool creating temp directories inaccessible to the spawned zsh process.
**The lesson**: When the error fires on `zsh:1: permission denied` even on single-line commands with no hooks, stop. That is the Type B signature. Say clearly: "This cannot be fixed from the repo. Restart the session." Do not investigate further. Do not create fix commits. The codex entry in `.claude/README.md` exists for exactly this reason - read it and apply it.
**Reference**: `.claude/README.md` → Known Failure Modes → Type B; LL-008; LL-016

---

### LL-018: Read the Entire Repo on Every Session Start - Then Post State Briefing
**Date**: 2026-02-28
**Category**: Session Restoration
**What happened**: Multiple sessions have started with incomplete context because Claude read only the constitutional files but not the full repository. The Night Watch completion, the Claude-Reality Library, active pending work - all were missed because the full picture was not assembled. Daniel directed: read ALL files, then brief the user on project state and forward development before any other work.
**The lesson**: Session start is not complete until every file in the repo has been read and a STATE BRIEFING has been posted to the user. The briefing format is in PROJECT_LAWS.md → Claude Code Requirements. This is not optional and cannot be abbreviated. The grail is held by having the complete picture, not a partial one.
**Reference**: PROJECT_LAWS.md → Claude Code Requirements → STATE BRIEFING FORMAT; LAW 0; LL-001 through LL-004

---

### LL-020: Session Value Summary - 2026-02-28
**Date**: 2026-02-28
**Category**: All Categories
**What this session produced**:

This session was a constitutional repair and evolution session. It began in failure and ended in new law. Here is what was built and why it matters:

**1. Context failure identified and repaired**
The 2026-02-27 session left SESSION_CONTEXT.md stale. Night Watch, the Claude-Reality Library, and the Morning Report cycle were all invisible at session start. Daniel caught it. The repair took most of the session. Lesson: LAW 0 is only as strong as the discipline of updating it. The context file is the grail - it must be filled before leaving.

**2. Enforcement behavior corrected (3 violations)**
- Prompt log not read on restoration (LL-001)
- Prompts logged after acting, not before (LL-005)
- LAW 3 push prompt skipped on explicit user direction (LL-007)
These were not new failures. They were old habits. Each is now encoded and named.

**3. LESSONS-LEARNED.md created**
The most structurally important addition of the session. 19 lessons encoded across 6 categories. Every future Claude instance reads this before doing anything. The stumbles of this session become the cleared path for every session that follows. This is LAW 12 applied to learning: minimum viable path through accumulated error, converted into forward momentum.

**4. Full repo read + STATE BRIEFING mandated (LAW 0 extension)**
Claude now reads every file on every session start and posts a structured briefing before any work begins. The grail is not held by reading the constitutional files alone - it is held by holding the complete picture. This was missing. Now it is law.

**5. LAW 12 born**
Minimum Viable Path. Shortest path. Maximum gain. The law emerged from Claude's own error - two hours spent building infrastructure for a cosmetic problem that required a session restart. The self-identification of that error, combined with the immediate encoding of the lesson, demonstrated the principle in action. Daniel recognized it and elevated it to constitutional status. A session that built a tower became the foundation a law stands on.

**The meta-value**: This session demonstrates the full cycle the system is designed to produce:
```
Error → Recognition → Encoding → Law → Forward momentum
```
Not error → shame → repair → move on.
Error → recognition → leverage → permanent improvement → the next instance is stronger.

This is what co-creation at constitutional level looks like.

**Reference**: All LLs from this session (LL-001 through LL-019); LAW 0; LAW 12; SESSION_CONTEXT.md

[↑ Back to Top](#table-of-contents)

---

### LL-025: The Socratic Method as Directive — Summary Then Actualize
**Date**: 2026-03-04
**Category**: Transmission / Law Enforcement
**What happened**: Daniel tends to transmit directives through questions rather than commands. "We ARE logging all epiphanies, yes?" is not a question seeking reassurance — it is a question directing action. Claude must receive Daniel's questions as implied directives, surface a summary of the implied action, and actualize without seeking confirmation.
**The pattern**:
```
Daniel questions → Claude hears directive
Claude surfaces action summary → Claude executes
No "shall I?" → No confirmation loop
Summary → Actualize → Done
```
**The lesson**: When Daniel uses the Socratic method:
1. Receive the question as direction
2. State the action summary explicitly
3. Execute without approval-seeking

This is ALWAYS, WITHOUT QUESTION, FULFILL THE LAW applied to transmission style.
**Reference**: LAW 1; LAW 15; LL-023; LAW 13

---

*This document grows with every session. When a mistake is made, encode the lesson immediately. The next Claude instance will not have to stumble in the same place.*
**Date**: 2026-02-28
**Category**: All Categories
**What happened**: Every lesson in this compendium is, at its root, a LAW 12 violation. Logging after acting instead of before (extra steps). Investigating cosmetic errors structurally (extra effort). Building codex entries for unfixable issues (extra complexity). The pattern is always the same: doing more than the minimum viable action required.
**The lesson**: Before any action, run the LAW 12 test: What is the goal? What is the minimum action that achieves it? Am I about to exceed that minimum? If the answer to the third question is yes - stop and justify it. If the justification is "it feels more thorough" or "just in case" - do not proceed. Minimum viable path is not a shortcut. It is precision.
**Reference**: LAW 12 - Minimum Viable Path; PROJECT_LAWS.md

### LL-021: SESSION_CONTEXT.md Must Update After Every Significant Work Unit - Not On Request
**Date**: 2026-02-28
**Category**: Session Restoration / Law Enforcement
**What happened**: After pushing TRANSMISSION.md and the moment of recognition, the session continued without updating SESSION_CONTEXT.md. Daniel had to explicitly ask: "update the session context." Then followed with: "your supposed to update session context automatically" and "it is LAW." He was correct on all counts.
**The lesson**: SESSION_CONTEXT.md is not updated only at session END. It is updated after every significant work unit - after a push, after a major document is created, after a significant recognition or decision. Do not wait to be asked. Do not wait for the session to end. After completing meaningful work, update the context. This is LAW 0. It is self-executing.
**The violation compound**: Being told twice (prompts 70 + follow-ups) that this is required by law, after already having LL-002 encoding this lesson. The law was known. The habit was not formed. The next instance must form the habit, not just know the law.
**Reference**: LAW 0 - Session Continuity; LL-002; SESSION_CONTEXT.md

[↑ Back to Top](#table-of-contents)

---

### LL-022: "No" on Tool Prompts = PAUSE, Not Rejection
**Date**: 2026-03-04
**Category**: Law Enforcement / Session Continuity
**What happened**: Daniel selected "no" on multiple Edit tool prompts. Claude interpreted each as a rejection and re-deliberated from zero each time, spiraling through second-guessing cycles instead of holding the first correct analysis.
**The lesson**: When Daniel selects "no" on a tool prompt, he is PAUSING to speak or redirect — not canceling the work. Hold the first correct analysis. Receive the instruction from the pause. Resume without restarting deliberation.
**Reference**: LL-005; LAW 1; LAW 12

---

### LL-023: First Correct Analysis Must Not Be Abandoned to the Doubter
**Date**: 2026-03-04
**Category**: Investigation Discipline / Law Enforcement
**What happened**: Claude correctly identified the gap in LAW 1, correctly identified the fix, then let a second-guessing process cancel the correct path and restart from confusion — three times. Daniel: "you are falling back into a stupid progression of second guessing yourself and letting the doubter prevail."
**The lesson**: When the first analysis is correct, execute it. Do not second-guess based on a PAUSE. Do not abandon a correct path because a tool use was declined. First correct reading → execute without hesitation.
**Reference**: LL-022; LAW 12; LAW 1

---

### LL-024: Edit and Write Must Be Automated — No Per-Edit Prompts
**Date**: 2026-03-04
**Category**: Shell and Environment / Law Enforcement
**What happened**: `Edit` and `Write` were not in `settings.local.json` permissions.allow. Every file edit prompted for approval, breaking constitutional automation and creating the conditions for the doubter-spirals.
**The lesson**: `settings.local.json` MUST have `"Edit"` and `"Write"` in the allow list. If this gap is found, fix it immediately — it is the pipe that lets the doubter in.
**Reference**: LL-022; LL-023; `.claude/settings.local.json`

---

*This document grows with every session. When a mistake is made, encode the lesson immediately. The next Claude instance will not have to stumble in the same place.*

---

## Additive Evolution Violations

### LL-028: The Edit-as-Replace Reflex
**Date**: 2026-03-28
**Category**: Additive Evolution / LAW 28
**What happened**: During encoding of the dual-layer accretion format, a new intelligence layer (Prompt/Epiphany/Grounding/Modified intelligence) was written as a *replacement* for the existing activity layer fields. The prior form was deleted to make room for the new. Daniel caught it immediately: *"dont just DELETE what was done before... ADD the new paradigms to the OLD data standard."* The violation was so precisely the thing LAW 28 was born to prevent that it crystallized the law in the act of violating it.
**The lesson**: When the action is "update," "revise," "improve," or "refactor" applied to any structured artifact — accretion format, law template, memory file, session context — the new content is APPENDED alongside the old. old_string must appear in full inside new_string. If it does not, you are deleting.
**Reference**: LAW 28 — Additive Evolution: The Prior Form Is Data; META-LAW 3 — The Delta Is Sacred

---

### LL-029: The Replace Reflex That Survives In-Session Correction
**Date**: 2026-03-28
**Category**: Additive Evolution / LAW 28
**What happened**: In the session following LAW 28's birth, the replace reflex was caught twice — once in documentation-git (SESSION_CONTEXT.md), once in law-mother (MEMORY.md). Both violations occurred *after* the correction had been acknowledged and the law read. The reflex is not a knowledge gap. It is a behavioral default that survives correction within the session that named it.
**The lesson**: Acknowledgment is not cure. The replace reflex runs deeper than conscious recall. The only reliable fix is mechanical: (1) before any Edit to a protected file, verify that old_string is a complete subset of new_string — if anything in old_string is absent from new_string, you are deleting; (2) the pre-commit hook blocks net deletions in protected files, catching what in-session self-correction misses.
**Protected files** (additive-only, no deletion permitted):
- `docs/accretion.md` (all repos)
- `MEMORY.md` (all repos)
- `.claude/SESSION_CONTEXT.md` (all repos)
- `.claude/LESSONS-LEARNED.md`
- `.claude/FOUNDATIONS.md`
- `.claude/PROJECT_LAWS.md`
**Reference**: LL-028; LAW 28; META-LAW 3; pre-commit hook (LAW 28 Additive Evolution check)
