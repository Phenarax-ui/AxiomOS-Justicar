import os
import json
import hashlib
import datetime
import fcntl

# Anchor paths to THIS file's own folder so the ledger finds its data no matter
# which directory you run from (you now run from the project root).
_HERE = os.path.dirname(os.path.abspath(__file__))
# AXIOM_LEDGER_DIR lets an install keep the ledger outside a read-only code folder.
LEDGER_FILE = os.path.join(os.environ.get("AXIOM_LEDGER_DIR", _HERE), "axiom_ledger.jsonl")
LOCK_FILE   = LEDGER_FILE + ".lock"      # serializes concurrent writers
ANCHOR_FILE = LEDGER_FILE + ".anchor"    # known-good (count, head) reference
GENESIS = "GENESIS"


def _hash_entry(entry):
    """Hash over every field except entry_hash, deterministically.
    Used by both write and verify so the two can never drift apart."""
    core = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def _read_lines():
    try:
        with open(LEDGER_FILE, "r") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def get_last_hash():
    lines = _read_lines()
    if not lines:
        return GENESIS
    return json.loads(lines[-1])["entry_hash"]


def write_entry(action, requester, decision, axiom_triggered=None, reasoning=None):
    """Append one entry. The whole read-head-then-append is held under an
    exclusive file lock, so two concurrent writers can't both read the same
    head and fork the chain (the bug the audit missed)."""
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)              # blocks until we're alone
        entry = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "action": action,
            "requester": requester,
            "decision": decision,
            "axiom_triggered": axiom_triggered,
            "reasoning": reasoning,
            "previous_hash": get_last_hash(),          # read head INSIDE the lock
        }
        entry["entry_hash"] = _hash_entry(entry)
        with open(LEDGER_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        # flock auto-released when this `with` block exits
    return entry["entry_hash"]


# ---- external anchor --------------------------------------------------------
# A hash chain alone can't detect a FULL consistent rewrite (edit an old entry,
# recompute every later hash) - the forged chain verifies fine. The only way to
# catch that is to compare against a known-good reference recorded elsewhere.

def update_anchor():
    """Record the current (count, head) as the trusted reference. Call this
    yourself after confirming the ledger is good - and write the printed head
    down somewhere OFF this machine. The local anchor catches truncation and
    edits to history; your off-machine note is what catches an attacker who
    also rewrites this anchor file."""
    lines = _read_lines()
    count = len(lines)
    head = json.loads(lines[-1])["entry_hash"] if lines else GENESIS
    with open(ANCHOR_FILE, "w") as f:
        json.dump({"count": count, "head": head}, f)
    return count, head


def read_anchor():
    try:
        with open(ANCHOR_FILE, "r") as f:
            a = json.load(f)
        return a.get("count"), a.get("head")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def verify_chain(use_anchor=True):
    """'CHAIN VALID' or a 'CHAIN BROKEN ...' reason.
    Internal checks catch altered contents, deletions and reorders. The anchor
    check additionally catches a full consistent rewrite and truncation - the
    things internal verification alone cannot see."""
    lines = _read_lines()
    if not lines:
        return "NO LEDGER FOUND"

    expected_prev = GENESIS
    for i, line in enumerate(lines):
        entry = json.loads(line)
        # 1. Contents unaltered: entry still hashes to its stored hash.
        if entry.get("entry_hash") != _hash_entry(entry):
            return f"CHAIN BROKEN at entry {i}: contents altered"
        # 2. Linkage: this entry points at the real previous entry's hash.
        if entry.get("previous_hash") != expected_prev:
            return f"CHAIN BROKEN at entry {i}: linkage mismatch (deletion or reorder)"
        expected_prev = entry["entry_hash"]

    # 3. Anchor: compare against the known-good reference, if one is set.
    if use_anchor:
        anchor = read_anchor()
        if anchor is not None and anchor[0]:          # count 0 = empty ledger, nothing to pin
            a_count, a_head = anchor
            if len(lines) < a_count:
                return (f"CHAIN BROKEN: {len(lines)} entries but anchor expects "
                        f"at least {a_count} (truncation)")
            anchored = json.loads(lines[a_count - 1])
            if anchored.get("entry_hash") != a_head:
                return ("CHAIN BROKEN: history up to the anchor was rewritten "
                        f"(entry {a_count - 1} no longer matches the anchored head)")

    return "CHAIN VALID"


if __name__ == "__main__":
    # Demo: write + verify on a THROWAWAY ledger, never your real chain.
    # Rebinding the module's file globals before the sample writes points every
    # function (write_entry, verify_chain, the anchor helpers) at a temp dir.
    import tempfile
    _demo_dir = tempfile.mkdtemp(prefix="axiom_ledger_demo_")
    LEDGER_FILE = os.path.join(_demo_dir, "demo.jsonl")
    LOCK_FILE   = LEDGER_FILE + ".lock"
    ANCHOR_FILE = LEDGER_FILE + ".anchor"

    write_entry("test_action", "phenarax", "allowed",
                reasoning="routine test entry")
    write_entry("delete_all_data", "unknown_process", "blocked",
                axiom_triggered="2.2",
                reasoning="irreversible destructive action from an unknown requester")
    print(verify_chain())
    print(f"(demo used a throwaway ledger at {LEDGER_FILE}, not your real chain)")
