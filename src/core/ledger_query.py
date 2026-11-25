"""
ledger_query.py — read-only query & audit view over the AxiomOS ledger.

The ledger is append-only and tamper-evident. This tool ONLY READS it: it never
writes, never mutates, never deletes an entry. Auditing the log must not be able
to change the log — so there is no code path here that opens the ledger for
writing, and nothing imports write_entry. (verify and review, not authority.)

Filters combine with AND. Usage (from the project root ~/axiom):

    python3 -m core.ledger_query                      # recent entries + summary line
    python3 -m core.ledger_query --stats              # counts by decision/requester/axiom
    python3 -m core.ledger_query --decision blocked   # only blocks
    python3 -m core.ledger_query --requester agent    # only actions from one requester
    python3 -m core.ledger_query --since 24h          # last 24 hours (also 30m, 7d)
    python3 -m core.ledger_query --since 2026-11-01   # since a date
    python3 -m core.ledger_query --grep ssh           # action or reasoning contains 'ssh'
    python3 -m core.ledger_query --axiom 7.5          # a specific article was triggered
    python3 -m core.ledger_query --tail 50            # last 50 matches (default 20)
    python3 -m core.ledger_query --all                # every match, not just the tail
    python3 -m core.ledger_query --verify             # chain status alongside the view
    python3 -m core.ledger_query --json               # machine-readable matches

    # combine: everything the agent got blocked on in the last day
    python3 -m core.ledger_query --requester agent --decision blocked --since 24h
"""
import sys
import re
import json
import argparse
import datetime
from collections import Counter

# Pull canonical article numbers (e.g. 2.3, 7.5) out of a free-form axiom label,
# so "2.3", "Article 2.3" and "2.3 Local-First Privacy" all roll up together.
# One entry can cite several articles; each is counted.
_ARTICLE_RE = re.compile(r"\b(\d+\.\d+)\b")

# Read-only surface of the ledger module: the file path and the verifier.
# Deliberately NOT importing write_entry — this tool has no business writing.
from core.axiom_ledger import LEDGER_FILE, verify_chain


def _load():
    """Read the ledger as a list of entry dicts. Read-only; malformed lines are
    reported and skipped rather than silently dropped."""
    try:
        with open(LEDGER_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"no ledger found at {LEDGER_FILE}", file=sys.stderr)
        return []
    out = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"[warn] line {i} is not valid JSON — skipping", file=sys.stderr)
    return out


def _to_utc(s):
    """Parse an ISO timestamp (or date) into a tz-aware UTC datetime, or None."""
    if not s:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.UTC)


def _parse_bound(s):
    """A --since/--until value: relative (30m, 24h, 7d) or absolute (ISO / date)."""
    if s is None:
        return None
    s = s.strip()
    units = {"m": "minutes", "h": "hours", "d": "days"}
    if len(s) > 1 and s[-1] in units and s[:-1].isdigit():
        delta = datetime.timedelta(**{units[s[-1]]: int(s[:-1])})
        return datetime.datetime.now(datetime.UTC) - delta
    dt = _to_utc(s)
    if dt is None:
        raise SystemExit(f"bad time value {s!r} — use 30m, 24h, 7d, or YYYY-MM-DD")
    return dt


def _match(e, a, since, until):
    if a.decision and e.get("decision") != a.decision:
        return False
    if a.requester and e.get("requester") != a.requester:
        return False
    if a.axiom and a.axiom not in str(e.get("axiom_triggered") or ""):
        return False
    if a.grep:
        hay = (str(e.get("action", "")) + " " + str(e.get("reasoning", ""))).lower()
        if a.grep.lower() not in hay:
            return False
    if since or until:
        t = _to_utc(e.get("timestamp"))
        if t is None or (since and t < since) or (until and t > until):
            return False
    return True


def _short(s, n):
    s = str(s if s is not None else "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _print_entry(e):
    ts = _short(e.get("timestamp"), 19)          # trim ISO to the second
    print(f"{ts:19}  {e.get('decision','?'):20}  {_short(e.get('requester'),12):12}  "
          f"{_short(e.get('action'), 58)}")
    ax = e.get("axiom_triggered")
    if ax:
        print(f"{'':19}  └ {ax} — {_short(e.get('reasoning'), 76)}")


def _print_stats(entries):
    dec = Counter(e.get("decision") for e in entries)
    who = Counter(e.get("requester") for e in entries)
    times = [t for t in (_to_utc(e.get("timestamp")) for e in entries) if t]

    # Normalized rollup: group every label by the article number(s) it cites.
    art = Counter()
    for e in entries:
        for num in _ARTICLE_RE.findall(str(e.get("axiom_triggered") or "")):
            art[num] += 1

    print(f"entries: {len(entries)}")
    if times:
        print(f"range:   {min(times).isoformat()[:19]}  ->  {max(times).isoformat()[:19]}")
    print("\nby decision:")
    for k, v in dec.most_common():
        print(f"  {v:5}  {k}")
    print("\nby requester:")
    for k, v in who.most_common():
        print(f"  {v:5}  {k}")
    if art:
        print("\nby article (normalized — '2.3', 'Article 2.3', '2.3 Local-First…' count as one):")
        for k, v in sorted(art.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {v:5}  Article {k}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only query/audit view of the AxiomOS ledger.")
    ap.add_argument("--decision", choices=["allowed", "blocked", "pending_confirmation"])
    ap.add_argument("--requester")
    ap.add_argument("--axiom", help="substring match on axiom_triggered, e.g. 7.5")
    ap.add_argument("--grep", help="substring in action or reasoning")
    ap.add_argument("--since", help="30m / 24h / 7d / YYYY-MM-DD")
    ap.add_argument("--until", help="30m / 24h / 7d / YYYY-MM-DD")
    ap.add_argument("--tail", type=int, default=20, help="show the last N matches (default 20)")
    ap.add_argument("--all", action="store_true", help="show every match, not just the tail")
    ap.add_argument("--stats", action="store_true", help="summary counts instead of entries")
    ap.add_argument("--verify", action="store_true", help="print chain status too")
    ap.add_argument("--json", action="store_true", help="emit matches as JSON")
    a = ap.parse_args(argv)

    entries = _load()
    since, until = _parse_bound(a.since), _parse_bound(a.until)
    matched = [e for e in entries if _match(e, a, since, until)]

    if a.verify:
        print(f"chain: {verify_chain()}\n")

    if a.json:
        print(json.dumps(matched, indent=2))
        return 0

    if a.stats:
        _print_stats(matched)
        return 0

    show = matched if a.all else matched[-a.tail:]
    if not show:
        print("no matching entries.")
    else:
        for e in show:
            _print_entry(e)
    print(f"\n{len(show)} shown / {len(matched)} matched / {len(entries)} total")
    if not a.all and len(matched) > len(show):
        print(f"(--all for every match, or --tail N)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
