#!/usr/bin/env python3
"""Metabase CLI - Swiss Army Knife for Metabase."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

USAGE = """\
Usage: metabase-cli.py [--json] <command> [options]

Global Options:
  --json                      Machine-readable JSON output (no colors)

Commands:

  inspect                     Show Metabase overview (version, stats, tree)
  diag                        Find duplicates, empty cards, broken links
  backup [-f FILE]            Backup all content to ZIP (default: timestamped)
  restore -f FILE [--db ID]   Restore from ZIP backup

  card list                   List all cards (id, name, display type)
  card get <id>               Get card details including SQL query
  card create                 Create new card with SQL
      --name NAME             Card name (required)
      --sql SQL               SQL query (required)
      --display TYPE          Display: table|bar|line|pie|scalar|area (default: table)
      --description TEXT      Optional description
  card update <id>            Update existing card
      --name NAME             New name
      --sql SQL               New SQL query
  card delete <id>            Delete card permanently

  dashboard list              List all dashboards
  dashboard get <id>          Get dashboard with card positions
  dashboard create            Create new dashboard
      --name NAME             Dashboard name (required)
      --description TEXT      Optional description
  dashboard add-card <dashboard_id> <card_id>
      --row N                 Row position (default: 0)
      --col N                 Column position (default: 0)
      --size-x N              Width in grid units (default: 12, max: 24)
      --size-y N              Height in grid units (default: 8)
  dashboard delete <id>       Delete dashboard permanently

  query "SQL"                 Execute SQL and show results

  config                      Generate .env.example file

Examples:
  metabase-cli.py inspect
  metabase-cli.py diag
  metabase-cli.py --json card list
  metabase-cli.py card create --name "Revenue" --sql "SELECT SUM(x) FROM t" --display bar
  metabase-cli.py dashboard add-card 5 42 --row 0 --col 12 --size-x 12

Environment:
  METABASE_URL                Metabase URL (default: http://localhost:3000)
  METABASE_ADMIN_EMAIL        Admin email
  METABASE_ADMIN_PASSWORD     Admin password
  Or create .env file in current directory."""

# --- Configuration ---

def load_env() -> None:
    """Load .env file from multiple locations (first found wins)."""
    search_paths = [
        Path.cwd() / ".env",                          # Current directory
        Path(__file__).resolve().parent / ".env",     # Script directory
        Path(__file__).resolve().parent.parent / ".env",  # Parent of script dir
    ]
    # Also search up from script location for project root
    for parent in Path(__file__).resolve().parents:
        if (parent / "CLAUDE.md").exists():
            search_paths.append(parent / ".env")
            break

    for env_path in search_paths:
        if env_path.exists():
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            return  # Stop after first .env found


load_env()

METABASE_URL = os.getenv("METABASE_URL") or os.getenv("METABASE_HOST") or "http://localhost:3000"
METABASE_USER = os.getenv("METABASE_ADMIN_EMAIL") or os.getenv("METABASE_USER") or ""
METABASE_PASS = os.getenv("METABASE_ADMIN_PASSWORD") or os.getenv("METABASE_PASS") or ""


# --- UI Helpers ---

class UI:
    """Terminal UI with colors."""

    G, Y, R, B, BOLD, NC = "\033[92m", "\033[93m", "\033[91m", "\033[94m", "\033[1m", "\033[0m"
    json_mode = False

    @classmethod
    def log(cls, symbol: str, color: str, msg: str) -> None:
        if not cls.json_mode:
            print(f"{color}{symbol} {msg}{cls.NC}")

    @classmethod
    def tree(cls, title: str, items: list, fmt=lambda x: x) -> None:
        if cls.json_mode or not items:
            return
        print(f"\n{cls.BOLD}{title}{cls.NC}")
        for i, item in enumerate(items):
            prefix = "└── " if i == len(items) - 1 else "├── "
            print(f"{prefix}{fmt(item)}")


def output_json(data: Any) -> None:
    """Output data as JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# --- Metabase Client ---

class MetabaseClient:
    """Metabase API client."""

    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.session_id: str | None = None
        self.database_id: int | None = None

    def login(self) -> bool:
        """Authenticate and get session token."""
        UI.log("→", UI.B, f"Connecting to Metabase ({self.url})...")
        res = self._request("POST", "/api/session", {
            "username": self.user,
            "password": self.password
        }, auth=False)
        if res and "id" in res:
            self.session_id = res["id"]
            self._cache_database_id()
            UI.log("✓", UI.G, "Connected successfully")
            return True
        UI.log("✗", UI.R, "Failed to connect. Check credentials or wait for Metabase to start.")
        return False

    def _cache_database_id(self) -> None:
        """Cache the Copper Pipes database ID."""
        dbs = self._unwrap(self._request("GET", "/api/database"))
        for db in dbs:
            if "copper" in db.get("name", "").lower():
                self.database_id = db["id"]
                break
        if not self.database_id and dbs:
            self.database_id = dbs[0]["id"]

    def _unwrap(self, res: Any) -> list:
        """Unwrap API response that might be paginated."""
        if isinstance(res, dict) and "data" in res:
            return res["data"]
        return res if isinstance(res, list) else []

    def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        auth: bool = True,
    ) -> dict | list | None:
        """Make HTTP request to Metabase API."""
        req = urllib.request.Request(f"{self.url}{path}", method=method)
        req.add_header("Content-Type", "application/json")
        if auth and self.session_id:
            req.add_header("X-Metabase-Session", self.session_id)
        try:
            body = json.dumps(data).encode("utf-8") if data else None
            with urllib.request.urlopen(req, data=body, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err_body = e.read().decode("utf-8", errors="ignore")
            UI.log("⚠", UI.Y, f"API Error {e.code}: {err_body[:100]}")
            return {"error": f"HTTP {e.code}", "message": err_body}
        except urllib.error.URLError as e:
            UI.log("⚠", UI.Y, f"Connection error: {e.reason}")
            return {"error": "Connection failed", "message": str(e.reason)}

    # --- Inspect & Verify ---

    def inspect(self) -> dict:
        """Get Metabase overview."""
        props = self._request("GET", "/api/session/properties") or {}
        cards = self._unwrap(self._request("GET", "/api/card"))
        dashes = self._unwrap(self._request("GET", "/api/dashboard"))
        dbs = self._unwrap(self._request("GET", "/api/database"))
        users = self._unwrap(self._request("GET", "/api/user"))

        # Get dashboard details
        dash_details = []
        for d in dashes:
            det = self._request("GET", f"/api/dashboard/{d['id']}")
            cnt = len(det.get("dashcards", det.get("ordered_cards", []))) if det else 0
            dash_details.append({"id": d["id"], "name": d["name"], "card_count": cnt})

        result = {
            "version": props.get("version", {}).get("tag"),
            "url": self.url,
            "cards": len(cards),
            "dashboards": len(dashes),
            "databases": len(dbs),
            "users": len(users),
            "dashboard_details": dash_details,
            "database_list": [{"id": db["id"], "name": db["name"]} for db in dbs],
            "user_list": [{"email": u.get("email"), "name": u.get("common_name")} for u in users],
        }

        if not UI.json_mode:
            print(f"\n{UI.BOLD}=== Metabase Overview ({result['version']}) ==={UI.NC}")
            print(f"URL: {self.url}")
            print(f"Stats: {result['cards']} cards, {result['dashboards']} dashboards, {result['databases']} databases")
            UI.tree("Dashboards", dash_details, lambda x: f"{x['name']} {UI.G}({x['card_count']} cards){UI.NC}")
            UI.tree("Databases", dbs, lambda x: f"{x['name']} (ID: {x['id']})")
            UI.tree("Users", users, lambda x: f"{x.get('common_name', x.get('email'))} ({x.get('email')})")

        return result

    def diag(self) -> dict:
        """Check integrity of dashboards and cards."""
        UI.log("→", UI.B, "Running Metabase diagnostics...")

        cards = self._unwrap(self._request("GET", "/api/card"))
        dashes = self._unwrap(self._request("GET", "/api/dashboard"))
        valid_card_ids = {c["id"] for c in cards}

        issues = []
        ok_dashboards = []

        # 1. Check for duplicate card names
        name_to_ids: dict[str, list[int]] = {}
        for c in cards:
            name = c.get("name", "")
            name_to_ids.setdefault(name, []).append(c["id"])

        duplicates = {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}
        if duplicates:
            UI.log("⚠", UI.Y, f"Found {len(duplicates)} duplicate card names:")
            for name, ids in duplicates.items():
                UI.log("  ", UI.Y, f"'{name}': IDs {ids}")

        # 2. Check for empty cards (no SQL query)
        empty_cards = []
        for c in cards:
            dq = c.get("dataset_query", {})
            # Native query - check for empty SQL
            if dq.get("type") == "native":
                sql = dq.get("native", {}).get("query", "")
                if not sql or not sql.strip():
                    empty_cards.append({"id": c["id"], "name": c.get("name")})
            # GUI query without source-table
            elif dq.get("type") == "query":
                if not dq.get("query", {}).get("source-table"):
                    empty_cards.append({"id": c["id"], "name": c.get("name")})
            # No query at all
            elif not dq:
                empty_cards.append({"id": c["id"], "name": c.get("name")})

        if empty_cards:
            UI.log("⚠", UI.Y, f"Found {len(empty_cards)} empty cards:")
            for ec in empty_cards:
                UI.log("  ", UI.Y, f"ID {ec['id']}: '{ec['name']}'")

        # 3. Check dashboard integrity
        for d in dashes:
            detailed = self._request("GET", f"/api/dashboard/{d['id']}")
            if not detailed:
                issues.append({"type": "dashboard_error", "dashboard": d["name"], "error": "Could not fetch details"})
                continue

            dash_cards = detailed.get("dashcards", detailed.get("ordered_cards", []))
            if not dash_cards:
                issues.append({"type": "empty_dashboard", "dashboard": d["name"], "id": d["id"]})
                UI.log("⚠", UI.Y, f"Dashboard '{d['name']}' (ID {d['id']}): empty")
                continue

            missing = [dc.get("card_id") for dc in dash_cards if dc.get("card_id") and dc["card_id"] not in valid_card_ids]
            if missing:
                issues.append({"type": "missing_cards", "dashboard": d["name"], "missing_card_ids": missing})
                UI.log("✗", UI.R, f"Dashboard '{d['name']}': {len(missing)} missing cards {missing}")
            else:
                ok_dashboards.append(d["name"])
                UI.log("✓", UI.G, f"Dashboard '{d['name']}': {len(dash_cards)} cards OK")

        # Build result
        has_problems = len(issues) > 0 or len(duplicates) > 0 or len(empty_cards) > 0

        result = {
            "cards_total": len(cards),
            "dashboards_total": len(dashes),
            "ok_dashboards": ok_dashboards,
            "duplicate_cards": duplicates,
            "empty_cards": empty_cards,
            "dashboard_issues": issues,
            "success": not has_problems,
        }

        if result["success"]:
            UI.log("✓", UI.G, "Diagnostics complete: All checks passed.")
        else:
            problem_count = len(issues) + len(duplicates) + len(empty_cards)
            UI.log("⚠", UI.Y, f"Diagnostics complete: {problem_count} issues found.")

        return result

    # --- Backup & Restore ---

    def backup(self, filepath: str | None = None) -> dict:
        """Backup all cards and dashboards to ZIP."""
        cards = self._unwrap(self._request("GET", "/api/card"))
        dashes_list = self._unwrap(self._request("GET", "/api/dashboard"))
        dashes = [self._request("GET", f"/api/dashboard/{d['id']}") for d in dashes_list]
        dashes = [d for d in dashes if d]

        fname = filepath or f"metabase_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        with zipfile.ZipFile(fname, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr("cards.json", json.dumps(cards, ensure_ascii=False, indent=2))
            zf.writestr("dashboards.json", json.dumps(dashes, ensure_ascii=False, indent=2))

        UI.log("✓", UI.G, f"Backup saved to {fname}")
        return {"file": fname, "cards": len(cards), "dashboards": len(dashes)}

    def restore(self, filepath: str, db_id: int | None = None) -> dict:
        """Restore content from backup ZIP."""
        if not os.path.exists(filepath):
            return {"error": f"File not found: {filepath}"}
        if not zipfile.is_zipfile(filepath):
            return {"error": f"Not a valid ZIP: {filepath}"}

        target_db = db_id or self.database_id or 1

        with zipfile.ZipFile(filepath, "r") as zf:
            cards = json.loads(zf.read("cards.json"))
            dashboards = json.loads(zf.read("dashboards.json"))

        # Restore cards (3 passes for dependencies)
        existing = {c["name"]: c["id"] for c in self._unwrap(self._request("GET", "/api/card"))}
        id_map = {str(c["id"]): existing[c["name"]] for c in cards if c["name"] in existing}
        to_restore = [c for c in cards if c["name"] not in existing]
        to_restore.sort(key=lambda x: x.get("id", 0))

        restored = 0
        for _ in range(3):
            if not to_restore:
                break
            rem = []
            for c in to_restore:
                payload = {**c, "collection_id": None}
                payload.pop("id", None)
                payload.pop("creator_id", None)
                payload.pop("created_at", None)
                payload["dataset_query"]["database"] = target_db

                dq = payload["dataset_query"]
                if dq.get("type") == "query" and "query" in dq:
                    st = dq["query"].get("source-table")
                    if isinstance(st, str) and st.startswith("card__"):
                        old_id = st.replace("card__", "")
                        if old_id in id_map:
                            dq["query"]["source-table"] = f"card__{id_map[old_id]}"
                        else:
                            rem.append(c)
                            continue

                res = self._request("POST", "/api/card", payload)
                if res and "id" in res:
                    id_map[str(c["id"])] = res["id"]
                    restored += 1
                else:
                    rem.append(c)
            to_restore = rem

        UI.log("✓", UI.G, f"Cards: {restored} restored, {len(cards) - len(to_restore) - restored} existing")

        # Restore dashboards
        dash_map = {d["name"]: d["id"] for d in self._unwrap(self._request("GET", "/api/dashboard"))}
        dash_restored = 0

        for d in dashboards:
            d_id = dash_map.get(d["name"])
            if not d_id:
                res = self._request("POST", "/api/dashboard", {"name": d["name"]})
                d_id = res.get("id") if res else None
                if d_id:
                    dash_restored += 1

            if not d_id:
                continue

            cards_payload = []
            for i, dc in enumerate(d.get("dashcards", d.get("ordered_cards", []))):
                cid = dc.get("card_id")
                if cid and str(cid) not in id_map:
                    continue
                ndc = {
                    "id": -(i + 1),
                    "row": dc.get("row", 0),
                    "col": dc.get("col", 0),
                    "size_x": dc.get("size_x", 4),
                    "size_y": dc.get("size_y", 4),
                    "visualization_settings": dc.get("visualization_settings", {}),
                    "parameter_mappings": dc.get("parameter_mappings", []),
                }
                if cid:
                    ndc["card_id"] = id_map[str(cid)]
                cards_payload.append(ndc)

            self._request("PUT", f"/api/dashboard/{d_id}/cards", {"cards": cards_payload})
            UI.log("→", UI.B, f"Dashboard '{d['name']}': {len(cards_payload)} cards")

        return {"cards_restored": restored, "dashboards_restored": dash_restored, "failed": len(to_restore)}

    # --- Cards ---

    def list_cards(self) -> list:
        """List all cards."""
        cards = self._unwrap(self._request("GET", "/api/card"))
        return [{"id": c["id"], "name": c["name"], "display": c.get("display")} for c in cards]

    def get_card(self, card_id: int) -> dict | None:
        """Get card details."""
        res = self._request("GET", f"/api/card/{card_id}")
        if not res or "error" in res:
            return res
        return {
            "id": res.get("id"),
            "name": res.get("name"),
            "description": res.get("description"),
            "display": res.get("display"),
            "database_id": res.get("database_id"),
            "query": res.get("dataset_query", {}).get("native", {}).get("query"),
            "visualization_settings": res.get("visualization_settings"),
        }

    def create_card(self, name: str, sql: str, display: str = "table", description: str | None = None) -> dict:
        """Create a new card with SQL query."""
        if not self.database_id:
            return {"error": "No database found"}
        payload = {
            "name": name,
            "type": "question",
            "display": display,
            "dataset_query": {"type": "native", "native": {"query": sql}, "database": self.database_id},
            "visualization_settings": {},
        }
        if description:
            payload["description"] = description
        res = self._request("POST", "/api/card", payload)
        if res and "id" in res:
            UI.log("✓", UI.G, f"Card created: {res['name']} (ID: {res['id']})")
            return {"id": res["id"], "name": res["name"], "status": "created"}
        return res or {"error": "Failed to create card"}

    def update_card(self, card_id: int, sql: str | None = None, name: str | None = None) -> dict:
        """Update card."""
        current = self._request("GET", f"/api/card/{card_id}")
        if not current or "error" in current:
            return current or {"error": "Card not found"}
        payload = {}
        if sql:
            dq = current.get("dataset_query", {})
            if "native" in dq:
                dq["native"]["query"] = sql
            payload["dataset_query"] = dq
        if name:
            payload["name"] = name
        if not payload:
            return {"error": "Nothing to update"}
        res = self._request("PUT", f"/api/card/{card_id}", payload)
        if res and "id" in res:
            UI.log("✓", UI.G, f"Card updated: ID {res['id']}")
            return {"id": res["id"], "status": "updated"}
        return res or {"error": "Failed to update"}

    def delete_card(self, card_id: int) -> dict:
        """Delete a card."""
        res = self._request("DELETE", f"/api/card/{card_id}")
        if res is None or res == {} or (isinstance(res, dict) and "error" not in res):
            UI.log("✓", UI.G, f"Card deleted: ID {card_id}")
            return {"id": card_id, "status": "deleted"}
        return res

    # --- Dashboards ---

    def list_dashboards(self) -> list:
        """List all dashboards."""
        dashes = self._unwrap(self._request("GET", "/api/dashboard"))
        return [{"id": d["id"], "name": d["name"]} for d in dashes]

    def get_dashboard(self, dashboard_id: int) -> dict | None:
        """Get dashboard with cards."""
        res = self._request("GET", f"/api/dashboard/{dashboard_id}")
        if not res or "error" in res:
            return res
        cards = []
        for dc in res.get("dashcards", res.get("ordered_cards", [])):
            cards.append({
                "dashcard_id": dc.get("id"),
                "card_id": dc.get("card_id"),
                "card_name": dc.get("card", {}).get("name") if dc.get("card") else None,
                "row": dc.get("row"),
                "col": dc.get("col"),
                "size_x": dc.get("size_x"),
                "size_y": dc.get("size_y"),
            })
        return {"id": res.get("id"), "name": res.get("name"), "description": res.get("description"), "cards": cards}

    def create_dashboard(self, name: str, description: str | None = None) -> dict:
        """Create a new dashboard."""
        payload = {"name": name}
        if description:
            payload["description"] = description
        res = self._request("POST", "/api/dashboard", payload)
        if res and "id" in res:
            UI.log("✓", UI.G, f"Dashboard created: {res['name']} (ID: {res['id']})")
            return {"id": res["id"], "name": res["name"], "status": "created"}
        return res or {"error": "Failed to create dashboard"}

    def add_card_to_dashboard(self, dashboard_id: int, card_id: int, row: int = 0, col: int = 0, size_x: int = 12, size_y: int = 8) -> dict:
        """Add card to dashboard."""
        payload = {"cardId": card_id, "row": row, "col": col, "size_x": size_x, "size_y": size_y}
        res = self._request("POST", f"/api/dashboard/{dashboard_id}/cards", payload)
        if res and "id" in res:
            UI.log("✓", UI.G, f"Card {card_id} added to dashboard {dashboard_id}")
            return {"dashcard_id": res["id"], "status": "added"}
        return res or {"error": "Failed to add card"}

    def delete_dashboard(self, dashboard_id: int) -> dict:
        """Delete a dashboard."""
        res = self._request("DELETE", f"/api/dashboard/{dashboard_id}")
        if res is None or res == {} or (isinstance(res, dict) and "error" not in res):
            UI.log("✓", UI.G, f"Dashboard deleted: ID {dashboard_id}")
            return {"id": dashboard_id, "status": "deleted"}
        return res

    # --- Query ---

    def query(self, sql: str) -> dict:
        """Execute ad-hoc SQL query."""
        if not self.database_id:
            return {"error": "No database found"}
        res = self._request("POST", "/api/dataset", {
            "database": self.database_id,
            "type": "native",
            "native": {"query": sql}
        })
        if not res or "error" in res:
            return res or {"error": "Query failed"}
        data = res.get("data", {})
        cols = [c.get("name") for c in data.get("cols", [])]
        rows = data.get("rows", [])
        result = {"columns": cols, "rows": rows[:100], "row_count": len(rows), "truncated": len(rows) > 100}

        # Pretty print in non-JSON mode
        if not UI.json_mode and rows:
            # Print header
            print(" | ".join(str(c) for c in cols))
            print("-" * (sum(len(str(c)) for c in cols) + 3 * (len(cols) - 1)))
            # Print rows
            for row in rows[:20]:
                print(" | ".join(str(v) for v in row))
            if len(rows) > 20:
                print(f"... ({len(rows)} rows total)")

        return result


# --- CLI ---

def main() -> int:
    # Show full usage if no args or --help
    if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
        print(USAGE.strip())
        return 0

    parser = argparse.ArgumentParser(description="Metabase CLI", add_help=False)
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")
    subparsers = parser.add_subparsers(dest="command")

    # Top-level commands
    subparsers.add_parser("inspect", help="Show Metabase overview")
    subparsers.add_parser("diag", help="Diagnostics: duplicates, empty cards, integrity")

    backup_p = subparsers.add_parser("backup", help="Backup to ZIP")
    backup_p.add_argument("-f", "--file", help="Output file")

    restore_p = subparsers.add_parser("restore", help="Restore from ZIP")
    restore_p.add_argument("-f", "--file", required=True, help="Backup file")
    restore_p.add_argument("--db", type=int, help="Target database ID")

    # Card commands
    card_p = subparsers.add_parser("card", help="Card operations")
    card_sub = card_p.add_subparsers(dest="action")
    card_sub.add_parser("list", help="List cards")
    card_get = card_sub.add_parser("get", help="Get card")
    card_get.add_argument("id", type=int)
    card_create = card_sub.add_parser("create", help="Create card")
    card_create.add_argument("--name", required=True)
    card_create.add_argument("--sql", required=True)
    card_create.add_argument("--display", default="table")
    card_create.add_argument("--description")
    card_update = card_sub.add_parser("update", help="Update card")
    card_update.add_argument("id", type=int)
    card_update.add_argument("--sql")
    card_update.add_argument("--name")
    card_delete = card_sub.add_parser("delete", help="Delete card")
    card_delete.add_argument("id", type=int)

    # Dashboard commands
    dash_p = subparsers.add_parser("dashboard", help="Dashboard operations")
    dash_sub = dash_p.add_subparsers(dest="action")
    dash_sub.add_parser("list", help="List dashboards")
    dash_get = dash_sub.add_parser("get", help="Get dashboard")
    dash_get.add_argument("id", type=int)
    dash_create = dash_sub.add_parser("create", help="Create dashboard")
    dash_create.add_argument("--name", required=True)
    dash_create.add_argument("--description")
    dash_add = dash_sub.add_parser("add-card", help="Add card to dashboard")
    dash_add.add_argument("dashboard_id", type=int)
    dash_add.add_argument("card_id", type=int)
    dash_add.add_argument("--row", type=int, default=0)
    dash_add.add_argument("--col", type=int, default=0)
    dash_add.add_argument("--size-x", type=int, default=12)
    dash_add.add_argument("--size-y", type=int, default=8)
    dash_delete = dash_sub.add_parser("delete", help="Delete dashboard")
    dash_delete.add_argument("id", type=int)

    # Query command
    query_p = subparsers.add_parser("query", help="Execute SQL")
    query_p.add_argument("sql")

    # Config command
    subparsers.add_parser("config", help="Generate .env.example file")

    args = parser.parse_args()

    if not args.command or args.help:
        print(USAGE.strip())
        return 0

    UI.json_mode = args.json

    # Config command (no credentials needed)
    if args.command == "config":
        env_example = Path.cwd() / ".env.example"
        if env_example.exists():
            if args.json:
                output_json({"error": f"File already exists: {env_example}"})
            else:
                UI.log("✗", UI.R, f"File already exists: {env_example}")
            return 1
        template = """\
# Metabase CLI Configuration
# Copy this file to .env and fill in your credentials

METABASE_URL=http://localhost:3000
METABASE_ADMIN_EMAIL=admin@example.com
METABASE_ADMIN_PASSWORD=your_password_here
"""
        env_example.write_text(template)
        if args.json:
            output_json({"file": str(env_example), "status": "created"})
        else:
            UI.log("✓", UI.G, f"Created {env_example}")
        return 0

    # Validate credentials
    if not METABASE_USER or not METABASE_PASS:
        if args.json:
            output_json({"error": "Missing METABASE_ADMIN_EMAIL or METABASE_ADMIN_PASSWORD"})
        else:
            UI.log("✗", UI.R, "Missing credentials in .env (METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD)")
        return 1

    client = MetabaseClient(METABASE_URL, METABASE_USER, METABASE_PASS)
    if not client.login():
        if args.json:
            output_json({"error": "Failed to connect to Metabase"})
        return 1

    result = None

    exit_code = 0

    if args.command == "inspect":
        result = client.inspect()
    elif args.command == "diag":
        result = client.diag()
        if not result.get("success"):
            exit_code = 1
    elif args.command == "backup":
        result = client.backup(args.file)
    elif args.command == "restore":
        result = client.restore(args.file, args.db)

    elif args.command == "card":
        if args.action == "list":
            result = client.list_cards()
        elif args.action == "get":
            result = client.get_card(args.id)
        elif args.action == "create":
            result = client.create_card(args.name, args.sql, args.display, args.description)
        elif args.action == "update":
            result = client.update_card(args.id, args.sql, args.name)
        elif args.action == "delete":
            result = client.delete_card(args.id)

    elif args.command == "dashboard":
        if args.action == "list":
            result = client.list_dashboards()
        elif args.action == "get":
            result = client.get_dashboard(args.id)
        elif args.action == "create":
            result = client.create_dashboard(args.name, args.description)
        elif args.action == "add-card":
            result = client.add_card_to_dashboard(args.dashboard_id, args.card_id, args.row, args.col, args.size_x, args.size_y)
        elif args.action == "delete":
            result = client.delete_dashboard(args.id)

    elif args.command == "query":
        result = client.query(args.sql)

    if args.json and result is not None:
        output_json(result)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
