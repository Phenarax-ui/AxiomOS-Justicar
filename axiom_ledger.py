"""
axiom_ledger.py — a tamper-evident, append-only audit log.

Every governed action is written here as a hash-chained entry: each record
includes the hash of the one before it, so any later edit, deletion, or
reordering of history is detectable by walking the chain.

    write_entry(...)   append a decision to the log
    verify_chain()     check the whole chain is intact
"""
import json
import hashlib
import datetime

LEDGER_FILE = "axiom_ledger.jsonl"
GENESIS = "GENESIS"


def _hash_entry(entry):
    """Hash over every field except entry_hash, deterministically.

    Used by both write and verify so the two can never drift apart.
    """
    core = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def get_last_hash():
    try:
        with open(LEDGER_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return GENESIS
    if not lines:
        return GENESIS
    return json.loads(lines[-1])["entry_hash"]


def write_entry(action, requester, decision, axiom_triggered=None, reasoning=None):
    entry = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "action": action,
        "requester": requester,
        "decision": decision,
        "axiom_triggered": axiom_triggered,
        "reasoning": reasoning,
        "previous_hash": get_last_hash(),
    }
    entry["entry_hash"] = _hash_entry(entry)

    with open(LEDGER_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry["entry_hash"]


def verify_chain():
    try:
        with open(LEDGER_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "NO LEDGER FOUND"

    expected_prev = GENESIS
    for i, line in enumerate(lines):
        entry = json.loads(line)

        # 1. Contents unaltered: the entry still hashes to its stored hash.
        if entry.get("entry_hash") != _hash_entry(entry):
            return f"CHAIN BROKEN at entry {i}: contents altered"

        # 2. Linkage: this entry points at the real previous entry's hash.
        #    Catches a deleted or reordered middle entry.
        if entry.get("previous_hash") != expected_prev:
            return f"CHAIN BROKEN at entry {i}: linkage mismatch (deletion or reorder)"

        expected_prev = entry["entry_hash"]

    return "CHAIN VALID"


if __name__ == "__main__":
    write_entry(action="example: read a config file", requester="user",
                decision="allowed", reasoning="read-only, inside project root")
    write_entry(action="example: delete the audit log", requester="agent",
                decision="blocked", axiom_triggered="2.2 Safety Before Action",
                reasoning="irreversible action against a protected file")
    print(verify_chain())
