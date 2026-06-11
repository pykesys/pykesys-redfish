# Constitutional Enforcement System

This directory contains the automated enforcement machinery for PROJECT LAWS.

## Structure

```
.claude/
├── PROJECT_LAWS.md              # The 10 immutable project laws
├── .enforcement/                # Enforcement scripts and tracking
│   ├── git-audit.sh            # Scans commits for violations
│   ├── auto-remediate.sh       # Auto-fixes detected violations
│   ├── session-tracker.json    # Tracks Claude sessions
│   ├── commit-registry.json    # Registry of all commits
│   └── signatures.json         # Cryptographic verification
├── .violations/                 # Violation reports
│   ├── active/                 # Unresolved violations
│   ├── remediated/             # Auto-fixed violations
│   └── violation-index.md      # Master violation log
├── .hooks/                      # Git hooks
│   ├── pre-commit              # Blocks violating commits
│   ├── post-commit             # Audits after commit
│   ├── pre-push                # Final check before push
│   └── install.sh              # Hook installer
└── .constitutional-template/   # Reusable template for other projects
```

## How It Works

### Layer 1: Prevention (Pre-Commit Hook)
- Checks staged files before commit
- Blocks commits that violate laws
- Immediate feedback to contributor

### Layer 2: Detection (Post-Commit Audit)
- Scans all commits since last Claude session
- Detects manual commits (no Co-Authored-By tag)
- Generates violation reports

### Layer 3: Remediation (Auto-Fix)
- Automatically fixes detected violations
- Generates missing documentation
- Adds TOC/BTT to docs
- Creates retroactive prompt logs
- Commits fixes automatically

### Layer 4: Verification (Cryptographic)
- Tracks all Claude commits
- Maintains signatures for tamper detection
- Builds merkle tree for audit trail

## Running Manually

### Audit Git History
```bash
.claude/.enforcement/git-audit.sh
```

### Auto-Fix Violations
```bash
.claude/.enforcement/auto-remediate.sh
```

### Install Hooks
```bash
.claude/.hooks/install.sh
```

## For Contributors

**The enforcement system operates automatically**. You don't need to interact with it directly.

If you commit without Claude:
- Pre-commit hook may block you if violations detected
- Post-commit audit will catch violations
- Auto-remediation will attempt fixes
- You'll see violation reports in `.claude/.violations/active/`

**Best practice**: Always use Claude Code for changes to ensure compliance.

---

**Note**: This directory is hidden (`.claude/`) but critical for project governance.

---

## Known Failure Modes and Remediation

### Shell Temp Directory Corruption

**Symptom**: `zsh: permission denied: /var/folders/.../T/claude-XXXX-cwd` appearing after git hook execution. Commits and pushes still succeed but the error pollutes output and signals a corrupted shell working directory state.

**Cause**: Two distinct sub-causes:

- *Type A - Orphaned temp dir*: A hook called `cd` at the process level, changing the persistent shell's CWD to the repo root. The shell can no longer return to its original temp CWD.
- *Type B - Restricted temp dir*: Claude Code's Bash tool creates a new temp CWD per invocation with macOS permissions that zsh rejects after the command completes. Structural - exists regardless of hook behavior.

**Impact**: Cosmetic. All git operations succeed. The error is zsh reporting it cannot verify its CWD on exit.

**Remediation - Type A (Orphaned temp dir)**:

```bash
# Step 1: Inspect the orphaned temp directory before removing it
ls -la /var/folders/zz/zyxvpxvq6csfxvn_n0000000000000/T/ | grep claude

# Step 2: Read contents for post-analysis
ls -la /var/folders/zz/zyxvpxvq6csfxvn_n0000000000000/T/claude-XXXX-cwd/

# Step 3: Remove the orphaned directory
rm -rf /var/folders/zz/zyxvpxvq6csfxvn_n0000000000000/T/claude-XXXX-cwd

# Step 4: Re-initialize - start a fresh Claude Code session
```

**Remediation - Type B (Structural)**:

The temp directory is recreated on every invocation with restrictive permissions. No in-session fix exists. Restart the Claude Code session to re-initialize the shell context.

**Principle**: When infrastructure state is corrupted or structurally broken:
1. **Inspect** - read the state before discarding (post-analysis value)
2. **Discard** - remove cleanly
3. **Re-initialize** - start fresh from a known good state

Do not attempt to repair corrupted temp state. The complexity cost exceeds the value.

**Prevention (Type A)**: Ensure all `cd` calls in hook scripts use subshells so the caller's CWD is not modified. See `git-audit.sh` `main()` for the correct pattern.

