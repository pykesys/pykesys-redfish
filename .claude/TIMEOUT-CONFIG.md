# Claude Configuration Notes

## Timeout Settings

**Default Timeout for Connection Operations**: 15 minutes (900,000 ms)

Applies to:
- Git operations (push, pull, fetch, clone)
- SSH connections
- Network operations
- Any long-running bash commands

**Usage**: When calling Bash tool with connection operations, use:
```json
{
  "timeout": 900000
}
```

**Rationale**: Prevents premature timeouts on slow network operations or large repositories.

**Set by**: User on 2026-02-20
**Context**: After GitHub Enterprise authentication attempts took too long

---

**Note**: This is a behavioral preference, not a Claude Code settings.json configuration. The timeout parameter must be passed explicitly to Bash tool calls.
