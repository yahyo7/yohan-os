"""Skills — prompt/instruction templates loaded dynamically at runtime.

The brief: tools and skills are loaded dynamically; no agent ships with hardcoded
tool lists (or, here, hardcoded prompts). A skill is a ``SKILL.md`` with YAML
frontmatter (name, description, model_role) and a body that is a prompt template
with ``{placeholder}`` fields. Agents load a skill by name and render it with
context, rather than embedding prompt strings in Python — so prompts can be
edited, versioned, and swapped without touching code.

Skills live in ``packages/skills/<name>/SKILL.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

_SKILLS_DIR = Path(__file__).resolve().parents[4] / "packages" / "skills"


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    model_role: str
    body: str

    def render(self, **context: object) -> str:
        """Fill the template's ``{placeholders}`` with context."""
        return self.body.format(**context)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body) from a ``---``-delimited markdown file."""
    if text.startswith("---"):
        _, frontmatter, body = text.split("---", 2)
        return yaml.safe_load(frontmatter) or {}, body.strip()
    return {}, text.strip()


@lru_cache
def load_skill(name: str, *, skills_dir: str | None = None) -> Skill:
    """Load and cache a skill by name from ``packages/skills/<name>/SKILL.md``."""
    base = Path(skills_dir) if skills_dir else _SKILLS_DIR
    meta, body = _split_frontmatter((base / name / "SKILL.md").read_text())
    return Skill(
        name=meta.get("name", name),
        description=meta.get("description", ""),
        model_role=meta.get("model_role", "worker"),
        body=body,
    )


def available_skills(skills_dir: str | None = None) -> list[str]:
    """Names of all skills discoverable on disk (dynamic — not a hardcoded list)."""
    base = Path(skills_dir) if skills_dir else _SKILLS_DIR
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "SKILL.md").exists())
