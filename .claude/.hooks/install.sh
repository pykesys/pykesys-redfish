#!/bin/bash
# Install Constitutional Enforcement Git Hooks

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR/../..")"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}⚖️  Installing Constitutional Enforcement Hooks${NC}"
echo ""

# Make hooks executable
chmod +x "$SCRIPT_DIR"/pre-commit
chmod +x "$SCRIPT_DIR"/post-commit
chmod +x "$SCRIPT_DIR"/pre-push

# Install hooks
ln -sf "../../.claude/.hooks/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
ln -sf "../../.claude/.hooks/post-commit" "$GIT_HOOKS_DIR/post-commit"
ln -sf "../../.claude/.hooks/pre-push" "$GIT_HOOKS_DIR/pre-push"

echo -e "${GREEN}✓ Installed: pre-commit hook${NC}"
echo -e "${GREEN}✓ Installed: post-commit hook${NC}"
echo -e "${GREEN}✓ Installed: pre-push hook${NC}"
echo ""
echo -e "${BLUE}Constitutional enforcement is now active!${NC}"
echo ""
echo "Hooks will:"
echo "  • Block commits that violate laws (pre-commit)"
echo "  • Audit commits after creation (post-commit)"
echo "  • Validate before push (pre-push)"
echo ""
echo "See: .claude/PROJECT_LAWS.md for details"
