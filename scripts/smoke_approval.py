"""Exercise the approval-as-events primitive against Redis.

Simulates the two halves: an agent parking on an approval gate, and an approver
(gateway/dashboard) publishing the decision. Prints the resolved Decision.

    uv run python scripts/smoke_approval.py            # grant
    uv run python scripts/smoke_approval.py deny       # deny
"""

from __future__ import annotations

import asyncio
import sys

from yohan_core import (
    Bus,
    Decision,
    new_request_id,
    publish_decision,
    wait_for_decision,
)


async def main(grant: bool) -> int:
    bus = Bus()
    await bus.connect()
    try:
        request_id = new_request_id()

        # Agent side: park on the gate.
        waiter = asyncio.create_task(
            wait_for_decision(bus, request_id, timeout_s=10)
        )
        await asyncio.sleep(0.2)  # ensure the waiter is tailing before we decide

        # Approver side: publish the decision.
        await publish_decision(
            bus,
            request_id=request_id,
            trace_id="trc_smoke",
            granted=grant,
            decided_by="smoke-approver",
        )

        decision: Decision = await waiter
        print(f"decision: {decision}")
        ok = decision.granted is grant
        print("round-trip OK" if ok else "MISMATCH")
        return 0 if ok else 1
    finally:
        await bus.aclose()


if __name__ == "__main__":
    grant = not (len(sys.argv) > 1 and sys.argv[1] == "deny")
    raise SystemExit(asyncio.run(main(grant)))
