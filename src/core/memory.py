"""
memory.py - a small knowledge graph + query engine over knowledge.db.

Pure SQLite (FTS5 + an edges table), so it needs no model and is safe to run
alongside a loaded LLM with OLLAMA_MAX_LOADED_MODELS=1. Coexists with the tables
research_agent.py already creates (knowledge, next_steps) — this only adds
facts, edges, and an FTS index.

Three operations:
    remember(content, edges)  - store a fact and optional graph edges
    recall(query)             - full-text search over facts AND research notes
    graph_query(node)         - traverse edges out from a node

Demo:
    python3 memory.py           # runs a self-contained demo on memory_demo.db
"""
import json
import sqlite3

DB_PATH = "knowledge.db"

# Fixed relation vocabulary — keeps an LLM from fragmenting the graph into
# "found_on" / "was found on" / "discovered at". Unknown relations fold to
# related_to, with the original kept in metadata.
RELATIONS = {
    "found_on", "in_scope_of", "affects", "uses_tech", "has_endpoint",
    "similar_to", "duplicate_of", "reported_to", "related_to", "note",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY,
    content     TEXT NOT NULL,
    source      TEXT DEFAULT 'agent',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY,
    src         TEXT NOT NULL,
    relation    TEXT NOT NULL,
    dst         TEXT NOT NULL,
    metadata    TEXT,
    source      TEXT DEFAULT 'agent',
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content, content='facts', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
"""


def _norm(entity):
    return str(entity).strip().lower()


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def remember(content, edges=None, source="agent"):
    """Store a fact plus optional graph edges.

    edges: a list of [src, relation, dst] (optionally a 4th metadata item),
    or a list of {"src":..., "relation":..., "dst":..., "metadata":...} dicts.
    """
    conn = connect()
    conn.execute("INSERT INTO facts (content, source) VALUES (?, ?)", (content, source))

    added = 0
    for e in (edges or []):
        if isinstance(e, dict):
            src, relation, dst = e.get("src"), e.get("relation"), e.get("dst")
            meta = e.get("metadata")
        else:
            src, relation, dst = e[0], e[1], e[2]
            meta = e[3] if len(e) > 3 else None
        if not (src and relation and dst):
            continue
        if relation not in RELATIONS:                 # keep the vocabulary fixed
            meta = {"original_relation": relation, "metadata": meta}
            relation = "related_to"
        conn.execute(
            "INSERT INTO edges (src, relation, dst, metadata, source) VALUES (?,?,?,?,?)",
            (_norm(src), relation, _norm(dst),
             json.dumps(meta) if meta is not None else None, source),
        )
        added += 1

    conn.commit()
    conn.close()
    return f"remembered a fact and {added} edge(s)"


def recall(query, limit=5):
    """Search memory for a query: stored facts, research notes, and graph edges.

    Uses FTS5 for word relevance AND a literal LIKE match, because FTS tokenizes
    on punctuation and would miss dotted hostnames/paths like 'app.target.com'.
    Also returns graph edges touching the query entity, so "what do you know
    about X" surfaces X's whole neighborhood.
    """
    conn = connect()
    out = []
    like = f"%{query}%"

    # facts via FTS5 (quoted so punctuation can't break the query syntax)
    try:
        safe = '"' + query.replace('"', '') + '"'
        rows = conn.execute(
            "SELECT content FROM facts_fts WHERE facts_fts MATCH ? LIMIT ?",
            (safe, limit),
        ).fetchall()
        out += [f"[fact] {r['content']}" for r in rows]
    except sqlite3.OperationalError:
        pass

    # facts via literal substring (catches dotted hostnames/paths FTS misses)
    rows = conn.execute(
        "SELECT content FROM facts WHERE content LIKE ? LIMIT ?", (like, limit)
    ).fetchall()
    for r in rows:
        line = f"[fact] {r['content']}"
        if line not in out:
            out.append(line)

    # existing research notes (the knowledge table isn't FTS-indexed, so LIKE)
    try:
        rows = conn.execute(
            "SELECT subtopic, summary FROM knowledge "
            "WHERE summary LIKE ? OR topic LIKE ? OR subtopic LIKE ? LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
        out += [f"[note:{r['subtopic']}] {r['summary'][:400]}" for r in rows]
    except sqlite3.OperationalError:
        pass  # knowledge table may not exist in a fresh db

    # graph edges touching the query entity
    n = _norm(query)
    rows = conn.execute(
        "SELECT src, relation, dst FROM edges WHERE src = ? OR dst = ? LIMIT ?",
        (n, n, limit * 3),
    ).fetchall()
    out += [f"[edge] {r['src']} --{r['relation']}--> {r['dst']}" for r in rows]

    conn.close()
    return "\n\n".join(out) or "No matches in memory."


def graph_query(node, relation=None, depth=1):
    """Return edges touching `node`, out to `depth` hops, optionally filtered by relation."""
    conn = connect()
    node = _norm(node)
    seen, frontier, lines = set(), {node}, []

    for _ in range(max(1, depth)):
        nxt = set()
        for n in frontier:
            if n in seen:
                continue
            seen.add(n)
            q = "SELECT src, relation, dst FROM edges WHERE (src = ? OR dst = ?)"
            params = [n, n]
            if relation:
                q += " AND relation = ?"
                params.append(relation)
            for r in conn.execute(q, params):
                lines.append(f"{r['src']} --{r['relation']}--> {r['dst']}")
                nxt.add(r["dst"]); nxt.add(r["src"])
        frontier = nxt - seen

    conn.close()
    deduped = list(dict.fromkeys(lines))             # dedup, keep order
    return "\n".join(deduped) or f"No edges for '{node}'."


if __name__ == "__main__":
    DB_PATH = "memory_demo.db"                        # isolate the demo from knowledge.db

    print("remember:", remember(
        "Found a reflected XSS in the search box of app.target.com for program 1.",
        edges=[
            ["reflected xss", "found_on", "app.target.com"],
            ["app.target.com", "in_scope_of", "program 1"],
            ["reflected xss", "affects", "search box"],
        ],
    ))
    print("remember:", remember(
        "app.target.com runs nginx and a React frontend.",
        edges=[["app.target.com", "uses_tech", "nginx"],
               ["app.target.com", "uses_tech", "react"]],
    ))

    print("\nrecall 'xss':\n" + recall("xss"))
    print("\ngraph_query 'app.target.com':\n" + graph_query("app.target.com"))
    print("\ngraph_query 'app.target.com' depth=2:\n" + graph_query("app.target.com", depth=2))
