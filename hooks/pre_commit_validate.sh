#!/bin/bash
# Pre-commit validation hook for MobiusForge agents.
# Runs tests and lint before allowing commits.
# Used as a Claude Code PreToolUse hook for the Bash tool.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only intercept git commit commands
if echo "$COMMAND" | grep -q 'git commit'; then
    # Run tests
    if command -v pytest &> /dev/null; then
        pytest --tb=short -q 2>&1
        if [ $? -ne 0 ]; then
            echo "Pre-commit check FAILED: tests not passing" >&2
            exit 2
        fi
    fi

    # Run lint
    if command -v ruff &> /dev/null; then
        ruff check . --quiet 2>&1
        if [ $? -ne 0 ]; then
            echo "Pre-commit check FAILED: lint errors found" >&2
            exit 2
        fi
    fi
fi

exit 0
