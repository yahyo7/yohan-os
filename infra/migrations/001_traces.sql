-- 001_traces — the source of truth.
--
-- Every event that flows across the bus is written here exactly once by the
-- trace writer (apps/trace_writer). The dashboard reads from this table and, in
-- later phases, replay reconstructs a run from it. That is why the five contract
-- fields are first-class columns (fast to filter/join) while the open payload
-- stays JSONB (schema-flexible per event type).
--
-- Applied automatically on trace-writer startup for dev convenience; also kept
-- here as a numbered migration so the schema history is explicit. (A full alembic
-- setup is deferred until the schema actually starts churning — one table doesn't
-- justify the machinery yet.)

CREATE TABLE IF NOT EXISTS traces (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    trace_id    TEXT        NOT NULL,
    agent_id    TEXT        NOT NULL,
    event_type  TEXT        NOT NULL,
    event_ts    TIMESTAMPTZ NOT NULL,          -- when the event was created
    payload     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    -- provenance / idempotency:
    stream      TEXT,                          -- redis stream it was read from
    entry_id    TEXT,                          -- redis stream entry id
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per (stream, entry_id): makes the writer's insert idempotent, so an
-- at-least-once redelivery after a crash can't duplicate a trace row.
CREATE UNIQUE INDEX IF NOT EXISTS traces_stream_entry_uidx
    ON traces (stream, entry_id);

-- The dashboard's common access patterns.
CREATE INDEX IF NOT EXISTS traces_trace_id_idx  ON traces (trace_id);
CREATE INDEX IF NOT EXISTS traces_event_type_idx ON traces (event_type);
CREATE INDEX IF NOT EXISTS traces_event_ts_idx   ON traces (event_ts);
