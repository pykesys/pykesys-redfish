#!/usr/bin/env bash
# ============================================================
# law-0-enforcer.sh — LAW 0 Stop Hook
# ============================================================
# PURPOSE: Enforce LAW 0 (Session Continuity) at turn completion
# TRIGGER: Stop (fires when Claude finishes a response turn)
# MECHANISM: Detects if significant work was done since
#            SESSION_CONTEXT.md was last updated. If so:
#            exits 1 → forces Claude to continue → LAW 0 runs.
#
# WHY THIS EXISTS:
#   The UserPromptSubmit hook injects constitutional context
#   at the START of every turn. But nothing fired at the END.
#   LAW 0 requires SESSION_CONTEXT.md to be updated after
#   significant work — but with no structural trigger, this
#   depended on memory, which fails under cognitive load.
#   This hook closes that gap permanently.
#
# DETECTION LOGIC:
#   Find files modified more recently than SESSION_CONTEXT.md.
#   Exclude: SESSION_CONTEXT.md itself, CONSTITUTION-VERSION.md
#   (count-only file), docs/prompts.md (LAW 1 domain, not LAW 0),
#   and .git/ internals.
#   If any significant files are newer → SESSION_CONTEXT.md is
#   stale → LAW 0 is pending.
#
# EXIT CODES:
#   0 = SESSION_CONTEXT.md current, turn may end
#   1 = SESSION_CONTEXT.md stale, forces continuation
#
# REFERENCES:
#   PROJECT_LAWS.md § LAW 0 — Session Continuity
#   .claude/.init/law.0 — LAW 0 service unit
#   CODEX.md § LAW-0
# ============================================================

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

# Only enforce inside a Constitutional Law Claude project
if [ -z "$REPO_ROOT" ] || [ ! -f "$REPO_ROOT/.claude/PROJECT_LAWS.md" ]; then
  exit 0
fi

SESSION_CONTEXT="$REPO_ROOT/.claude/SESSION_CONTEXT.md"

# SESSION_CONTEXT.md must exist for LAW 0 to apply
if [ ! -f "$SESSION_CONTEXT" ]; then
  exit 0
fi

# ──────────────────────────────────────────────────────────
# Find files modified more recently than SESSION_CONTEXT.md
#
# Excluded from triggering (not "significant work" for LAW 0):
#   SESSION_CONTEXT.md       — the file we're checking
#   CONSTITUTION-VERSION.md  — count registry only
#   docs/prompts.md          — LAW 1 domain (prompt logging)
#   .git/                    — git internals
#   *.log                    — log files
# ──────────────────────────────────────────────────────────
NEWER_FILES=$(find "$REPO_ROOT" \
  -not -path "*/.git/*" \
  -not -name "SESSION_CONTEXT.md" \
  -not -name "CONSTITUTION-VERSION.md" \
  -not -path "*/.claude/log/prompts.md" \
  -not -name "*.log" \
  -newer "$SESSION_CONTEXT" \
  -type f \
  2>/dev/null | head -8)

if [ -z "$NEWER_FILES" ]; then
  # Nothing newer than SESSION_CONTEXT.md — LAW 0 honored
  exit 0
fi

# ──────────────────────────────────────────────────────────
# Significant work detected — SESSION_CONTEXT.md is stale
# LAW 0 VIOLATION — force continuation to execute the update
# ──────────────────────────────────────────────────────────
RELATIVE_FILES=$(echo "$NEWER_FILES" | sed "s|$REPO_ROOT/||g")

cat <<EOF
⚖️  LAW 0 ENFORCEMENT — Session Continuity

Files modified since last SESSION_CONTEXT.md update:
$RELATIVE_FILES

LAW 0 (Session Continuity) is ACTIVE. SESSION_CONTEXT.md must
reflect the current session state before this turn closes.

ACTION: Update SESSION_CONTEXT.md now — automatic, unconditional.
Record: what was built, what changed, current last commit, prompt count.
No asking. No deferring. This is the Law.
EOF

exit 1
