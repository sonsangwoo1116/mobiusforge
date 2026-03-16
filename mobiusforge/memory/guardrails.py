"""Guardrails file manager (FR-011)."""

from __future__ import annotations

from pathlib import Path


class GuardrailsManager:
    """Manages .mobiusforge/guardrails.md — accumulated project rules."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> str:
        if self.path.exists():
            return self.path.read_text(encoding="utf-8")
        return ""

    def add_rule(self, rule: str, category: str = "general") -> None:
        """Append a new guardrail rule."""
        existing = self.load()
        if rule in existing:
            return  # Already exists

        if not existing:
            existing = "# Project Guardrails\n\n"

        existing += f"\n## {category}\n- {rule}\n"
        self.path.write_text(existing, encoding="utf-8")

    def init_default(self) -> None:
        """Create a default guardrails file if none exists."""
        if self.path.exists():
            return

        content = """# Project Guardrails

## Code Quality
- All code must have tests
- No print() debugging — use logger
- Max file size: 300 lines

## Safety
- Never hardcode API keys or secrets
- Always validate external input
- Use try/except for external calls

## Git
- One logical change per commit
- Descriptive commit messages
- Never commit .env or secrets
"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")
