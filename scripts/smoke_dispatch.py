"""Fan out N tasks to the echo agent in parallel and gather results by task_id.

Start the echo agent first (scripts/run_echo.sh), then run this. Proves the
dispatch helper's parallel fan-out / fan-in.

    uv run python scripts/smoke_dispatch.py
"""

from __future__ import annotations

import asyncio

from yohan_core import Bus, Task, dispatch, new_trace_id


async def main() -> int:
    bus = Bus()
    await bus.connect()
    try:
        trace_id = new_trace_id()
        tasks = [Task(agent_type="echo", payload={"text": f"task-{i}"}) for i in range(3)]

        results = await dispatch(
            bus, trace_id=trace_id, agent_id="supervisor-smoke", tasks=tasks, timeout_s=15
        )

        print(f"dispatched {len(tasks)}, collected {len(results)}")
        for task in tasks:
            ev = results.get(task.task_id)
            reply = ev.payload.get("reply") if ev else "(missing)"
            print(f"  {task.task_id} → {reply}")
        ok = len(results) == len(tasks) and all(
            results[t.task_id].payload.get("reply") == f"echo: {t.payload['text']}"
            for t in tasks
        )
        print("all tasks gathered correctly ✓" if ok else "DISPATCH FAILED")
        return 0 if ok else 1
    finally:
        await bus.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
