# MCP Server Observability Reference

> **Load when:** Designing a new server, auditing an existing one for a tool-surface review,
> or planning the first post-MVP iteration.
>
> **Scope:** UNIVERSAL principle; OPINIONATED implementation defaults.

---

## Why log tool calls

A production MCP server is a UI for agents — and like any UI, you cannot tune it without
usage data. Three concrete decisions need numbers, not intuition:

1. **Dead tools** — surface bloat hides high-value tools. Tools called 0–2 times across
   thousands of sessions are usually not discoverable, not useful, or both. **Caveat:** a
   correctness-critical tool can legitimately fire rarely (emergency rollback, one-shot
   setup, fallback for an unusual error path). Before deleting, confirm low frequency is
   not "low frequency of *needing* it". Otherwise, rewrite the description first (likely
   cause: agents do not understand when to call it); remove if a follow-up window still
   shows zero calls.
2. **Hot tools** — traffic typically concentrates in a handful of tools (commonly the top
   3–5, sometimes more depending on surface shape). Their descriptions and error messages
   have the highest leverage. Find your own top-N from the log and invest there first.
3. **Error-prone tools** — high error rate per call signals an agent UX bug, not a backend
   bug. Look at the `Action:` hint, parameter shape, or required prerequisites.

Without a usage log, the only signal is qualitative feedback and operator gut feeling.
`submit_feedback` is a useful pattern when there is a maintainer who actively reads the queue;
without that, the log is the only durable signal. Either way, neither alone is enough to
decide what to cut.

The audit-checklist `80/20 check` is the consumer of this data. Do not run a tool-surface
audit without it.

---

## What to record per call

Minimal, useful, safe:

| Field | Purpose | Notes |
|-------|---------|-------|
| `ts` | When | ISO-8601 or epoch ms |
| `tool_name` | Which tool | Exact registered name |
| `caller_id` | Who | Session/principal/agent id if available; null is fine |
| `duration_ms` | Latency | Measure server-side, not transport |
| `status` | `ok` / `error` | Mirror `isError` |
| `error_class` | Kind of failure | Short label: `validation`, `upstream_timeout`, `not_found`, `permission`, etc. Not the full message |
| `args_shape` | Optional, schema-only | `["dialog_id", "limit"]` — which args were provided, NOT their values |
| `result_size` | Optional | Bytes or item count, for pagination tuning |

Do **NOT** log:

- Raw argument values — they may contain secrets, PII, or prompt-injected content that you
  later display in a dashboard and trigger the injection on a human reviewer
- Full response bodies — same reason, plus disk cost
- Full error messages verbatim if the message echoes user data — log the class, store the
  message in a separate, access-controlled error log if you need it

If you need to correlate to args without storing them, hash them with a server-only salt
and log the hash. Same args → same hash, no recoverable values.

---

## Where to store *(OPINIONATED defaults)*

Three patterns, pick the one that matches the project. Decision summary:

| Situation | Pattern |
|-----------|---------|
| No DB, want minimum moving parts | **A** — JSONL on disk |
| Server already has SQLite or Postgres | **B** — separate `tool_calls` table |
| OTel / Loki / Datadog already operated for other services | **C** — structured log to existing stack |

If unsure, start with **A**. JSONL migrates cleanly into B or C later; B/C do not migrate cleanly back to A. Do not adopt Pattern C just because it sounds production-grade — it is overhead unless the pipeline already exists.

### Pattern A — JSONL on disk *(stateless servers, no DB)*

One line per call to a log file. Trivial to ship; queryable with `jq` or DuckDB
(`SELECT tool_name, COUNT(*) FROM read_json_auto('calls.jsonl') GROUP BY 1 ORDER BY 2 DESC`).

```python
log_event({"ts": ..., "tool_name": "search_messages", "status": "ok", "duration_ms": 142})
```

Rotate daily, retain 30–90 days. For stdio servers, this MUST be a file or stderr — never
stdout (see security-threats.md transport rule).

Analysis example — error rate and p95 latency per tool with `jq` and `awk`:

```bash
# Error rate per tool (requires jq + sort + uniq)
jq -r '[.tool_name, .status] | @tsv' calls.jsonl \
  | awk '{calls[$1]++; if($2=="error") errs[$1]++} END {for(t in calls) printf "%s\t%.2f\n", t, errs[t]/calls[t]}' \
  | sort -k2 -rn

# p95 latency per tool with DuckDB (an embedded analytical SQL database — no server,
# single file, fast aggregations; think SQLite for OLAP)
duckdb -c "SELECT tool_name,
             QUANTILE_CONT(duration_ms, 0.95) AS p95_ms,
             COUNT(*) AS calls
           FROM read_json_auto('calls.jsonl')
           GROUP BY tool_name ORDER BY p95_ms DESC"
```

### Pattern B — separate SQLite/Postgres table *(servers that already have a DB)*

A dedicated `tool_calls` table, isolated from the server's main schema:

```sql
CREATE TABLE tool_calls (
  id          INTEGER PRIMARY KEY,
  ts          TIMESTAMP NOT NULL,
  tool_name   TEXT NOT NULL,
  caller_id   TEXT,
  duration_ms INTEGER NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('ok', 'error')),
  error_class TEXT,
  args_shape  TEXT,           -- JSON array
  result_size INTEGER
);
CREATE INDEX idx_tool_calls_ts_name ON tool_calls (ts, tool_name);
```

Separate from app data so retention/cleanup is independent and a usage-stats query never
locks production tables. Mirror the `submit_feedback` storage pattern — different concern,
different table.

### Pattern C — structured log to existing stack *(Loki, OTel, Datadog already in place)*

**When this is worth it:** multi-service deployment, distributed traces across process
boundaries, or when you already operate an OTel collector. **Skip if:** single-server MCP,
low volume, no existing OTel infrastructure — Pattern A or B will give you more signal per
hour of work.

Emit JSON events; let the existing pipeline handle storage, retention, and dashboards. Use
Loki/Promtail labels or OTel attributes for `tool_name` and `status` so queries fan out
correctly.

For OTel servers, also emit a span per call: span name = `mcp.tool.<tool_name>`, attributes
include `mcp.tool.status` and `mcp.tool.error_class`. The MCP host can correlate to upstream
spans automatically.

---

## Reports to run

Four queries cover most decisions:

1. **Top-N by call count** — confirms which tools matter
2. **Dead tools** — call_count = 0 or < 1% of median over a window long enough for the
   median to be statistically meaningful — for a tool called occasionally that may mean a
   longer window; for hot tools, a shorter one suffices
3. **Error rate per tool** — `errors / total` > 10% sustained over 30 minutes AND > 20
   errors in that window is a smell; look at `error_class` distribution. At low volume
   (< 20 calls/window) alert on absolute error count instead — 10% means nothing on 5 calls
4. **Latency p50 / p95 per tool** — agents time out on slow tools and abandon them; the
   tool then looks "dead" in metric 2

```sql
-- Dead tools (30-day window)
SELECT t.name, COUNT(c.id) AS calls
FROM declared_tools t
LEFT JOIN tool_calls c
  ON c.tool_name = t.name
  AND c.ts > now() - interval '30 days'
GROUP BY t.name
ORDER BY calls ASC;

-- Error rate per tool
SELECT tool_name,
       COUNT(*)                                       AS calls,
       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS error_rate
FROM tool_calls
WHERE ts > now() - interval '30 days'
GROUP BY tool_name
HAVING COUNT(*) > 20
ORDER BY error_rate DESC;
```

`declared_tools` can be a one-row-per-tool table you sync at startup, or hard-code the list
in the report — the point is to see tools with **zero** calls, which absent-from-log queries
miss.

---

## What to do with the numbers

Reports without actions are dashboards-as-theatre. Tie each metric to a concrete decision:

| Signal | Action |
|--------|--------|
| Zero or near-zero calls over 30 days | Rewrite description (add "Use when…" trigger, examples). Re-measure. If still dead next quarter — delete. |
| Top-3 tools concentrate >50% traffic | Audit their descriptions, error messages, defaults first — this is where leverage lives |
| Two tools with similar names + overlapping callers | Candidate for consolidation into one tool with a `mode=` parameter |
| Error rate > 10% with same `error_class` dominant | Fix the schema / add validation / add `Action:` hint pointing at the prerequisite tool |
| p95 latency exceeds the agent's wait tolerance for this tool's perceived cost | Return an async handle (job id) and a status tool, or paginate harder |
| `submit_feedback` mentions a tool that has high error rate in the log | Two channels agree — high-priority fix |

The qualitative channel (`submit_feedback`) and the quantitative channel (usage log) are
complementary. Feedback tells you *why* something is wrong; usage log tells you *whether* it
matters at scale.

---

## Implementation notes

- Instrument at the framework boundary — single decorator/middleware around the tool dispatch
  loop, not per-tool. Per-tool instrumentation drifts.
- Record the event in a `finally` block so errors and exceptions are captured the same way
  as successes.
- Logging must never fail the call. Wrap the log write in `try/except` and discard on
  failure; an observability bug should not break the product.
- For stdio servers, the log writer must not touch stdout (corrupts JSON-RPC framing — see
  security-threats.md).
- If the server is multi-process (daemon + on-demand MCP), the on-demand process emits to
  the daemon over its socket, the daemon writes the log. Same as the daemon-architecture
  pattern for application logs.

---

## Quick check

- [ ] Every tool call produces a log/event with at minimum `ts`, `tool_name`, `status`, `duration_ms`
- [ ] No raw argument values, no full response bodies, no secrets in the log
- [ ] A 30-day "dead tools" query has been run at least once and acted on
- [ ] Error rate and p95 latency are queryable per tool
- [ ] Log writes cannot fail the tool call
