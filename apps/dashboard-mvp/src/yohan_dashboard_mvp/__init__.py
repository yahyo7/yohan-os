"""yohan_dashboard_mvp — a minimal read-only view over the traces table.

Deliberately thin and disposable: it reads from Postgres (the source of truth),
never from the bus directly, so it can't perturb the system it observes. The
real dashboard (Next.js + React Flow + SSE) arrives in Phase 5 and this gets
deleted. Keeping it dumb now is the point — it exists to unblock development.
"""
