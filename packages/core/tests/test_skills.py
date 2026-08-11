"""Skill loader — frontmatter parsing, rendering, discovery. No services."""

from __future__ import annotations

import textwrap

import pytest

from yohan_core.skills import Skill, available_skills, load_skill


def _write_skill(dir_, name, body):
    d = dir_ / name
    d.mkdir()
    (d / "SKILL.md").write_text(body)


def test_load_parses_frontmatter_and_body(tmp_path):
    _write_skill(
        tmp_path,
        "greet",
        textwrap.dedent(
            """\
            ---
            name: greet
            description: say hi
            model_role: classifier
            ---
            Hello {who}, welcome.
            """
        ),
    )
    skill = load_skill("greet", skills_dir=str(tmp_path))
    assert skill.name == "greet"
    assert skill.description == "say hi"
    assert skill.model_role == "classifier"
    assert skill.render(who="Sam") == "Hello Sam, welcome."


def test_model_role_defaults_to_worker(tmp_path):
    _write_skill(tmp_path, "x", "---\nname: x\n---\nbody {a}")
    assert load_skill("x", skills_dir=str(tmp_path)).model_role == "worker"


def test_available_skills_discovers_dynamically(tmp_path):
    _write_skill(tmp_path, "a", "---\nname: a\n---\nA")
    _write_skill(tmp_path, "b", "---\nname: b\n---\nB")
    assert available_skills(str(tmp_path)) == ["a", "b"]


def test_repo_ships_the_three_phase4_skills():
    """The real packages/skills must contain the three skills agents load."""
    names = available_skills()
    for expected in ("triage_classify", "triage_draft", "morning_briefing"):
        assert expected in names, names
    # And they load + expose a model_role.
    assert load_skill("triage_classify").model_role == "classifier"


def test_render_is_pure():
    s = Skill(name="n", description="d", model_role="worker", body="{x}-{y}")
    assert s.render(x="1", y="2") == "1-2"
