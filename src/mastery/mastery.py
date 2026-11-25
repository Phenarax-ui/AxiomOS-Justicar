"""
mastery.py - the scoring brain of the tutor. No Ollama, no network.

Tracks how well you know each concept with a Leitner box system:
every concept sits in a box 0-5. Answer correctly and it moves up a box
(you'll see it less often). Miss it and it drops to box 0 (you'll see it
again soon). The tutor always drills your weakest, stalest concept.

Concepts are also grouped into difficulty TIERS (foundations / intermediate
/ advanced). The picker only offers tiers you've unlocked: you drill a tier
until every concept in it is solid (box >= UNLOCK_BOX), and only then does the
next tier start appearing. Leitner spacing still applies within the unlocked
tiers - this just stops the tutor from throwing decorators at you while you're
still on lists.

Because this file never calls the model, the whole scoring system is
testable without Ollama running - same reason creatures.py has no Discord
in it. That seam is what lets you trust the scoring independently of
whatever the model happens to say.
"""
import json
import os
import time

from curriculum import CONCEPTS

PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mastery_v3.json")  # your private profile (git-ignored)
MAX_BOX = 5


# ── difficulty tiers ────────────────────────────────────────────────────────
# A tier's concepts must all reach box >= UNLOCK_BOX before the next tier opens.
# If you add a concept to curriculum.py, list it here too, or it falls back to
# tier 1 (shows up in the foundations group).
UNLOCK_BOX = 3

LEVELS = {
    1: [  # foundations
        "lists", "list_methods_iteration", "dictionaries", "while_loops",
        "functions", "file_io", "error_handling", "classes", "modules",
    ],
    2: [  # intermediate
        "strings_advanced", "list_comprehensions", "nested_data_structures",
        "function_advanced", "scope_closures", "iterators_generators",
        "decorators", "context_managers", "comprehensions_advanced",
        "working_with_json", "working_with_files_advanced", "working_with_csv",
        "command_line_args", "http_requests", "regular_expressions",
    ],
    3: [  # advanced
        "oop_advanced", "dunder_methods", "error_handling_advanced", "testing",
        "type_hints", "dataclasses", "concurrency_basics",
        "working_with_databases", "virtual_environments",
    ],
}

_LEVEL_OF = {key: lvl for lvl, keys in LEVELS.items() for key in keys}


def concept_level(key):
    """Difficulty tier of a concept (1 = foundations). Unlisted keys -> 1."""
    return _LEVEL_OF.get(key, 1)


def load_profile():
    """Read the saved profile, or start a fresh empty one."""
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return {}


def save_profile(profile):
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)


def _entry(profile, key):
    """Return a concept's record, creating a blank one the first time."""
    if key not in profile:
        profile[key] = {"box": 0, "seen": 0, "correct": 0, "last_seen": 0}
    return profile[key]


def current_level(profile, domain=None):
    """Highest tier currently unlocked. Tier 1 is always open; tier N+1 opens
    only once every concept in tier N (for this domain) is at box >= UNLOCK_BOX."""
    unlocked = min(LEVELS)
    for lvl in sorted(LEVELS):
        unlocked = lvl
        keys = [k for k in LEVELS[lvl]
                if k in CONCEPTS and (domain is None or CONCEPTS[k]["domain"] == domain)]
        if not keys:
            continue                      # nothing in this tier for this domain → skip past it
        if not all(profile.get(k, {}).get("box", 0) >= UNLOCK_BOX for k in keys):
            break                         # tier not solid yet → don't open the next one
    return unlocked


def pick_concept(profile, domain=None):
    """Choose what to drill next: among the UNLOCKED tiers only, pick the
    weakest (lowest box), ties broken by whichever was seen longest ago.
    Returns a concept key, or None if the domain has no unlocked concepts."""
    unlocked = current_level(profile, domain)
    keys = [k for k, c in CONCEPTS.items()
            if (domain is None or c["domain"] == domain)
            and concept_level(k) <= unlocked]
    if not keys:
        return None

    def rank(k):
        e = profile.get(k, {"box": 0, "last_seen": 0})
        return (e["box"], e["last_seen"])      # weakest + stalest sorts first

    return min(keys, key=rank)


def note_attempt(profile, key, verdict):
    """Record ONE answered question: bump the seen/correct tallies and the
    timestamp. Deliberately does NOT move the box - box changes happen per
    study SESSION (pass_session / fail_session below), because one lucky
    question isn't mastery. Reps are."""
    e = _entry(profile, key)
    e["seen"] += 1
    e["last_seen"] = int(time.time())
    if verdict == "CORRECT":
        e["correct"] += 1
    return e


def pass_session(profile, key):
    """You cleared a concept this round (got enough correct reps). Climb a box.
    Five passed sessions = fully mastered."""
    e = _entry(profile, key)
    e["box"] = min(e["box"] + 1, MAX_BOX)
    return e


def fail_session(profile, key):
    """You ran out of tries without enough correct reps. Drop a box (floor 0)
    so it resurfaces sooner - but one rough round doesn't wipe all progress."""
    e = _entry(profile, key)
    e["box"] = max(e["box"] - 1, 0)
    return e


def progress(profile, domain=None):
    """Return (mastered, total) where mastered = concepts at the top box."""
    keys = [k for k, c in CONCEPTS.items() if domain is None or c["domain"] == domain]
    mastered = sum(1 for k in keys if profile.get(k, {}).get("box", 0) >= MAX_BOX)
    return mastered, len(keys)
