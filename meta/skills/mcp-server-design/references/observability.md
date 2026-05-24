# MCP Server Observability Reference

> Load when designing logging or running a tool-surface review. UNIVERSAL principle, OPINIONATED implementation defaults.

---

## What the log is for

Three decisions the log unlocks (consumer: `audit-checklist.md §80/20 check`):

- **Dead tools** — 0–2 calls across thousands of sessions = undiscoverable, useless, or both. *Caveat:* correctness-critical tools (emergency rollback, one-shot setup, rare-error fallback) can legitimately fire rarely. Rewrite the description first; delete only if the next window still shows zero.
- **Hot tools** — traffic concentrates in 3–5 tools. Their descriptions and error messages have highest leverage. Audit those first.
- **Error-prone tools** — high error rate signals an agent UX bug, not a backend bug. Inspect the `Action:` hint, parameter shape, or missing prerequisites.

---

## What to record per call

Minimal, useful, safe. The four-field minimum (`ts`, `tool_name`, `status`, `duration_ms`) is the bar SKILL.md enforces; the rest are upgrades.

| Field | Required? | Purpose | Notes |
|-------|-----------|---------|-------|
| `ts` | **required** | When | ISO-8601 or epoch ms |
| `tool_name` | **required** | Which tool | Exact registered name |
| `status` | **required** | `ok` / `error` | Mirror `isError` |
| `duration_ms` | **required** | Latency | Measure server-side, not transport |
| `caller_id` | optional | Who | Authenticated principal where available, else session id, else null. Required if per-principal rate-limits in [security-threats.md §5](security-threats.md#5-resource-exhaustion-and-dos) are in scope — `null` is fine for the log but not enough for principal-level limits. |
| `error_class` | optional | Kind of failure | Short label: `validation`, `upstream_timeout`, `not_found`, `permission`, etc. Not the full message |
| `args_shape` | optional | Schema-only | `["dialog_id", "limit"]` — which args were provided, NOT their values |
| `result_size` | optional | Pagination tuning | Bytes or item count |

Do **NOT** log:

- Raw argument values — may contain secrets/PII (see [security-threats.md §6 — Secret hygiene](security-threats.md#6-secret-hygiene--mcp-specific-leak-surfaces)) or attacker-injected content (see [security-threats.md §1 — Untrusted data flowing through your server](security-threats.md#1-untrusted-data-flowing-through-your-server))
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

Rotate daily, retain 30–90 days. **Which process owns the log file depends on transport:**
under `stdio`, the MCP server writes the JSONL itself (never to `stdout` — corrupts the
transport); under the daemon + on-demand pattern, the daemon owns the JSONL via its socket
and the MCP process must not write logs at all. Canonical channel rule:
[daemon-architecture.md §Stderr Rule](daemon-architecture.md#stderr-rule-reversed-under-this-pattern).
File path is your choice — typical: `~/.<server>/logs/calls.jsonl` (per-user) or
`/var/log/<server>/calls.jsonl` (system).

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

## Signal → action

| Signal | Action |
|--------|--------|
| Zero or near-zero calls over 30 days | Rewrite description (add "Use when…" trigger, examples). Re-measure. If still dead next quarter — delete. |
| Top-3 tools concentrate >50% traffic | Audit their descriptions, error messages, defaults first — this is where leverage lives |
| Two tools with similar names + overlapping callers | Candidate for consolidation into one tool with a `mode=` parameter |
| Error rate > 10% with same `error_class` dominant | Fix the schema / add validation / add `Action:` hint pointing at the prerequisite tool |
| p95 latency exceeds the agent's wait tolerance for this tool's perceived cost | Return an async handle (job id) and a status tool, or paginate harder |
| `submit_feedback` mentions a tool with high log error rate | Two channels agree — high-priority fix |

`submit_feedback` tells you *why*; the usage log tells you *whether* it matters at scale.

---

## Implementation notes

- Instrument at the framework boundary — single decorator/middleware around the tool dispatch
  loop, not per-tool. Per-tool instrumentation drifts.
- Record the event in a `finally` block so errors and exceptions are captured the same way
  as successes.
- Logging must never fail the call. Wrap the log write in `try/except` and discard on
  failure; an observability bug should not break the product.
- Stdio transport rule and the daemon-pattern exception (socket-based logging) are canonical in
  [daemon-architecture.md §Stderr Rule](daemon-architecture.md#stderr-rule-reversed-under-this-pattern).

---

## Quick check

- [ ] Every tool call produces a log/event with at minimum `ts`, `tool_name`, `status`, `duration_ms`
- [ ] No raw argument values, no full response bodies, no secrets in the log
- [ ] A 30-day "dead tools" query has been run at least once and acted on
- [ ] Error rate and p95 latency are queryable per tool
- [ ] Log writes cannot fail the tool call
