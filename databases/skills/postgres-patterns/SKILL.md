---
name: postgres-patterns
description: This skill should be used when the user asks to "write PostgreSQL query", "optimize postgres query", "use LATERAL join", "use CTE", "window functions in postgres", "explain analyze", "postgres performance", "rewrite SQL query", "postgres local variables", "advanced SQL patterns", mentions "PostgreSQL", "psql", or needs guidance on idiomatic PostgreSQL query patterns beyond basic SELECT/JOIN.
---

# PostgreSQL Patterns

Idiomatic patterns that make PostgreSQL queries cleaner, faster, and more maintainable. Each pattern includes the problem it solves, the solution, and when NOT to use it.

## LATERAL as Local Variables

`CROSS JOIN LATERAL` lets you compute intermediate values once and reuse them — like local variables in a procedural language, but inside pure SQL.

**Problem:** Repeated subexpressions clutter queries and invite copy-paste bugs:

```sql
-- BAD: expression repeated 3 times
SELECT
  (price * quantity * (1 - discount / 100)) AS total,
  (price * quantity * (1 - discount / 100)) * tax_rate AS tax,
  (price * quantity * (1 - discount / 100)) * (1 + tax_rate) AS grand_total
FROM orders;
```

**Solution:** Extract into a LATERAL subquery:

```sql
SELECT o.*, v.total, v.total * o.tax_rate AS tax, v.total * (1 + o.tax_rate) AS grand_total
FROM orders o
CROSS JOIN LATERAL (
  SELECT o.price * o.quantity * (1 - o.discount / 100) AS total
) v;
```

You can chain multiple LATERAL subqueries — each can reference the previous:

```sql
SELECT *
FROM orders o
CROSS JOIN LATERAL (SELECT o.price * o.quantity AS subtotal) s
CROSS JOIN LATERAL (SELECT s.subtotal * (1 - o.discount / 100) AS discounted) d
CROSS JOIN LATERAL (SELECT d.discounted * (1 + o.tax_rate) AS grand_total) g;
```

**When to use:** 3+ references to the same computed value. Complex multi-step calculations.
**When NOT to use:** Simple one-off expressions. The overhead of LATERAL isn't worth it for a single reuse.

**Performance:** `CROSS JOIN LATERAL` with a pure expression (no table access) is optimized away by the planner — zero runtime cost. Verify with `EXPLAIN`.

## CTE Chaining

Common Table Expressions (`WITH`) break complex queries into named, readable steps. PostgreSQL 12+ treats CTEs as inline by default (no optimization fence).

```sql
WITH
  active_users AS (
    SELECT id, email, created_at
    FROM users
    WHERE status = 'active' AND last_login > now() - interval '30 days'
  ),
  user_orders AS (
    SELECT u.id, u.email, count(*) AS order_count, sum(o.total) AS revenue
    FROM active_users u
    JOIN orders o ON o.user_id = u.id
    WHERE o.created_at > now() - interval '90 days'
    GROUP BY u.id, u.email
  )
SELECT email, order_count, revenue
FROM user_orders
WHERE revenue > 1000
ORDER BY revenue DESC;
```

**Materialized CTEs:** Force materialization when the CTE is referenced multiple times and you want to avoid re-computation:

```sql
WITH expensive_calc AS MATERIALIZED (
  SELECT id, heavy_function(data) AS result FROM big_table
)
SELECT * FROM expensive_calc WHERE result > 100
UNION ALL
SELECT * FROM expensive_calc WHERE result < -100;
```

**When to use:** Multi-step transformations, self-documenting queries, reusing a subquery result.
**When NOT to use:** Don't wrap a simple subquery in a CTE just for style — it adds noise without clarity.

## EXPLAIN ANALYZE Basics

Always measure before optimizing. `EXPLAIN ANALYZE` runs the query and shows actual timings.

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Key fields to watch:
- **actual time** — first row vs all rows (startup cost vs total)
- **rows** — actual vs estimated. Large mismatch = stale statistics → run `ANALYZE table_name`
- **Buffers: shared hit/read** — hits = cached, reads = disk I/O
- **Seq Scan** on large tables — usually wants an index
- **Sort Method: external merge** — not enough `work_mem`

**Pattern:** Compare before/after:

```sql
-- Before
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE user_id = 42;
-- Add index
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders(user_id);
-- After
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE user_id = 42;
```

**Caution:** `ANALYZE` actually executes the query. For `UPDATE`/`DELETE`, wrap in a transaction and roll back:

```sql
BEGIN;
EXPLAIN (ANALYZE, BUFFERS) DELETE FROM orders WHERE created_at < '2020-01-01';
ROLLBACK;
```

## Window Functions

Window functions compute values across related rows without collapsing them — unlike `GROUP BY`.

**Running total:**

```sql
SELECT date, amount,
  sum(amount) OVER (ORDER BY date) AS running_total
FROM transactions;
```

**Rank within groups:**

```sql
SELECT department, employee, salary,
  rank() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank
FROM employees;
```

**Compare to previous row:**

```sql
SELECT date, revenue,
  revenue - lag(revenue) OVER (ORDER BY date) AS daily_change,
  round(100.0 * (revenue - lag(revenue) OVER (ORDER BY date)) / lag(revenue) OVER (ORDER BY date), 1) AS pct_change
FROM daily_revenue;
```

Cleaner with a named window:

```sql
SELECT date, revenue,
  revenue - lag(revenue) OVER w AS daily_change,
  round(100.0 * (revenue - lag(revenue) OVER w) / lag(revenue) OVER w, 1) AS pct_change
FROM daily_revenue
WINDOW w AS (ORDER BY date);
```

**Common window functions:** `row_number()`, `rank()`, `dense_rank()`, `lag()`, `lead()`, `first_value()`, `last_value()`, `nth_value()`, `ntile()`.

## Index Patterns

**Partial indexes** — index only the rows you query:

```sql
-- Only index active orders (80% of queries, 20% of data)
CREATE INDEX idx_orders_active ON orders(created_at)
  WHERE status = 'active';
```

**Covering indexes** — include columns to enable index-only scans:

```sql
CREATE INDEX idx_users_email ON users(email) INCLUDE (name, status);
-- This query never touches the heap:
SELECT name, status FROM users WHERE email = 'foo@bar.com';
```

**Expression indexes** — index computed values:

```sql
CREATE INDEX idx_users_lower_email ON users(lower(email));
-- Now this uses the index:
SELECT * FROM users WHERE lower(email) = 'foo@bar.com';
```

**GIN for containment queries** (arrays, JSONB, full-text):

```sql
CREATE INDEX idx_tags ON articles USING GIN(tags);
SELECT * FROM articles WHERE tags @> ARRAY['postgresql'];
```

**When to add indexes:** After identifying slow queries via `pg_stat_statements` or `EXPLAIN ANALYZE`. Not preemptively — every index slows writes.
