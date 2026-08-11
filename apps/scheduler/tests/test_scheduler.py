"""Scheduler due-detection + config loading. Pure logic, no bus/clock."""

from __future__ import annotations

import textwrap
from datetime import datetime
from zoneinfo import ZoneInfo

from yohan_scheduler.scheduler import due_fire_time, load_jobs

_KST = ZoneInfo("Asia/Seoul")


def test_fires_when_a_boundary_passed_since_last():
    now = datetime(2026, 8, 11, 7, 0, 30, tzinfo=_KST)   # just after 07:00
    last = datetime(2026, 8, 11, 6, 0, 0, tzinfo=_KST)   # fired at 06:00
    fire = due_fire_time("0 7 * * *", now, last)
    assert fire is not None and fire.hour == 7 and fire.minute == 0


def test_does_not_refire_same_boundary():
    now = datetime(2026, 8, 11, 7, 5, 0, tzinfo=_KST)
    last = datetime(2026, 8, 11, 7, 0, 0, tzinfo=_KST)   # already fired 07:00
    assert due_fire_time("0 7 * * *", now, last) is None


def test_not_due_before_boundary():
    now = datetime(2026, 8, 11, 6, 59, 0, tzinfo=_KST)
    last = datetime(2026, 8, 11, 6, 0, 0, tzinfo=_KST)
    # Most recent boundary is yesterday 07:00, which is before last (06:00 today)?
    # No — yesterday 07:00 < 06:00 today is false; it's earlier, so not newer.
    assert due_fire_time("0 7 * * *", now, last) is None


def test_load_jobs(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(
        textwrap.dedent(
            """
            jobs:
              - name: brief
                cron: "0 7 * * *"
                tz: Asia/Seoul
                agent: supervisor
                text: morning briefing
                chat_id: 42
            """
        )
    )
    jobs = load_jobs(p)
    assert len(jobs) == 1
    assert jobs[0].agent == "supervisor" and jobs[0].chat_id == 42
