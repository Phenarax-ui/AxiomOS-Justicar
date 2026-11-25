"""
db_query.py — read-only inspector / query for the AxiomOS SQLite databases.

Safety, so this can never hurt your data:
  * Each DB is opened with SQLite's read-only URI (file:...?mode=ro). The
    CONNECTION itself cannot write — even a DROP is refused by the handle, not
    just by a string check. That's the strong guarantee.
  * Only SELECT / WITH statements are run (a second layer on top of mode=ro).
  * Only an allowlisted set of databases can be opened — nothing else on disk.

Databases: bounty (bounty.db), leads (leads.db).

Run (from the project root ~/axiom):
    python3 -m core.db_query --list                       # databases it knows
    python3 -m core.db_query bounty --schema              # tables + columns
    python3 -m core.db_query leads  --table leads --limit 20
    python3 -m core.db_query leads  --sql "SELECT title, score, status FROM leads WHERE score >= 7 ORDER BY score DESC"
    python3 -m core.db_query bounty --sql "SELECT name, payout_notes FROM programs"
"""
import os
import sys
import sqlite3
import argparse

# Databases live in the project root (one level up from core/).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATABASES = {
    "bounty": os.path.join(_ROOT, "bounty.db"),
    "leads":  os.path.join(_ROOT, "leads.db"),
}

MAXW = 48   # cap column width so wide text stays readable


def _connect_ro(name):
    path = _DATABASES.get(name)
    if path is None:
        raise SystemExit(f"unknown database '{name}'. Known: {', '.join(_DATABASES)}")
    if not os.path.exists(path):
        raise SystemExit(f"database file not found: {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)   # read-only handle
    con.row_factory = sqlite3.Row
    return con


def _is_read_only(sql):
    s = sql.strip().lstrip("(").strip().lower()
    return s.startswith("select") or s.startswith("with")


def _print_rows(headers, rows):
    if not rows:
        print("(no rows)")
        return
    widths = [len(h) for h in headers]
    cells = []
    for r in rows:
        vals = ["" if r[i] is None else str(r[i]) for i in range(len(headers))]
        cells.append(vals)
        for i, v in enumerate(vals):
            widths[i] = min(max(widths[i], len(v)), MAXW)

    def line(vals):
        return "  ".join(v[:MAXW].ljust(widths[i]) for i, v in enumerate(vals))

    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for vals in cells:
        print(line(vals))
    print(f"\n{len(rows)} row(s)")


def _tables(con):
    return [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]


def show_schema(name):
    con = _connect_ro(name)
    tables = _tables(con)
    if not tables:
        print(f"(no tables in {name})")
    for t in tables:
        print(f"\nTABLE {t}")
        for col in con.execute(f"PRAGMA table_info({t})"):   # t is a real table name
            flags = ""
            if col["pk"]:
                flags += " PK"
            if col["notnull"]:
                flags += " NOT NULL"
            print(f"  {col['name']:14} {col['type'] or '':10}{flags}")
    con.close()


def browse(name, table, limit):
    con = _connect_ro(name)
    real = set(_tables(con))
    if table not in real:
        con.close()
        raise SystemExit(f"no table '{table}' in {name}. Tables: {', '.join(sorted(real))}")
    cur = con.execute(f"SELECT * FROM {table} LIMIT {int(limit)}")   # table validated above
    headers = [d[0] for d in cur.description]
    _print_rows(headers, cur.fetchall())
    con.close()


def run_sql(name, sql):
    if not _is_read_only(sql):
        raise SystemExit("only SELECT / WITH queries are allowed here.")
    con = _connect_ro(name)
    try:
        cur = con.execute(sql)
    except sqlite3.Error as e:
        con.close()
        raise SystemExit(f"query error: {e}")
    headers = [d[0] for d in cur.description] if cur.description else []
    _print_rows(headers, cur.fetchall())
    con.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only inspector/query for AxiomOS databases.")
    ap.add_argument("database", nargs="?", help="which db: " + ", ".join(_DATABASES))
    ap.add_argument("--list", action="store_true", help="list the known databases")
    ap.add_argument("--schema", action="store_true", help="show tables and columns")
    ap.add_argument("--table", help="browse all rows of a table (with --limit)")
    ap.add_argument("--sql", help="run a read-only SELECT / WITH query")
    ap.add_argument("--limit", type=int, default=50, help="row cap for --table (default 50)")
    a = ap.parse_args(argv)

    if a.list or not a.database:
        print("databases:")
        for k, v in _DATABASES.items():
            print(f"  {k:8} -> {v}  [{'ok' if os.path.exists(v) else 'MISSING'}]")
        return 0
    if a.database not in _DATABASES:
        raise SystemExit(f"unknown database '{a.database}'. Known: {', '.join(_DATABASES)}")

    if a.table:
        browse(a.database, a.table, a.limit)
    elif a.sql:
        run_sql(a.database, a.sql)
    else:
        show_schema(a.database)          # default action: show the schema
    return 0


if __name__ == "__main__":
    sys.exit(main())
