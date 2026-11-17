"""
memory.py — a small knowledge graph + query engine.

Pure SQLite (an edges table + FTS5), so it needs no model and is safe to run
alongside a loaded LLM. Gives a governed agent durable memory across sessions:

    remember(content, edges)  store a fact and optional typed relations
    recall(query)             full-text search over stored facts
    graph_query(node)         traverse the relations out from a node
"""
import json
import sqlite3

DB_PATH = "memory.db"

# A small fixed relation vocabulary keeps an LLM from fragmenting the graph into
# synonyms ("depends_on" / "needs" / "requires"). Unknown relations fold to
# relates_to, with the original preserved in metadata. Edit to taste.
RELATIONS = {
    "relates_to", "part_of", "depends_on", "caused_by", "instance_of",
    "located_in", "similar_to", "note",
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

    edges: a list of [src, relation, dst] (optional 4th metadata item), or a
    list of {"src":..., "relation":..., "dst":..., "metadata":...} dicts.
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
            relation = "relates_to"
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
    """Search stored facts: FTS5 for word relevance plus a literal match, so
    punctuation-heavy terms (hostnames, paths) aren't missed. Also returns graph
    edges touching the query entity."""
    conn = connect()
    out = []
    like = f"%{query}%"

    try:
        safe = '"' + query.replace('"', '') + '"'
        rows = conn.execute(
            "SELECT content FROM facts_fts WHERE facts_fts MATCH ? LIMIT ?", (safe, limit)
        ).fetchall()
        out += [f"[fact] {r['content']}" for r in rows]
    except sqlite3.OperationalError:
        pass

    rows = conn.execute(
        "SELECT content FROM facts WHERE content LIKE ? LIMIT ?", (like, limit)
    ).fetchall()
    for r in rows:
        line = f"[fact] {r['content']}"
        if line not in out:
            out.append(line)

    n = _norm(query)
    rows = conn.execute(
        "SELECT src, relation, dst FROM edges WHERE src = ? OR dst = ? LIMIT ?",
        (n, n, limit * 3),
    ).fetchall()
    out += [f"[edge] {r['src']} --{r['relation']}--> {r['dst']}" for r in rows]

    conn.close()
    return "\n\n".join(out) or "No matches in memory."


def graph_query(node, relation=None, depth=1):
    """Return edges touching `node`, out to `depth` hops, optionally filtered."""
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
    deduped = list(dict.fromkeys(lines))
    return "\n".join(deduped) or f"No edges for '{node}'."


if __name__ == "__main__":
    DB_PATH = "memory_demo.db"
    print(remember(
        "The billing service depends on the auth service and runs in the us-west region.",
        edges=[["billing service", "depends_on", "auth service"],
               ["billing service", "located_in", "us-west"]],
    ))
    print("\nrecall 'auth':\n" + recall("auth"))
    print("\ngraph_query 'billing service' depth=2:\n" + graph_query("billing service", depth=2))
