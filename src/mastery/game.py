"""
game.py - the motivation layer. Pure, no model, no network (like mastery.py).

mastery.py decides what you actually KNOW (Leitner boxes + tiers). This sits on
top and makes grinding it feel like a game: XP for every right answer, a streak
that multiplies that XP as you chain corrects, an overall level with a progress
bar, and bonuses for clearing concepts, writing code, and unlocking whole tiers.
None of it changes what you learn - it just makes the grind not feel like a grind.

Game state lives under profile['_game'], saved and loaded with everything else.
The underscore keeps it clear of real concept keys, so mastery.py never trips
over it.
"""

# ── XP economy (tune to taste) ──────────────────────────────────────────────
XP_CORRECT     = 10     # one right answer (before streak bonus)
XP_PASS        = 40     # clearing a concept (a box up)
XP_CODE        = 50     # passing a code challenge - you WROTE it
XP_TIER_UNLOCK = 200    # opening a whole new tier

STREAK_STEP = 0.10      # each extra point of streak adds 10% to a correct answer
STREAK_CAP  = 2.0       # ...up to 2x


def _state(profile):
    g = profile.setdefault("_game", {})
    g.setdefault("xp", 0)
    g.setdefault("level", 1)
    g.setdefault("streak", 0)
    g.setdefault("best_streak", 0)
    return g


def xp_for_level(lvl):
    """Total XP needed to REACH a level. Rising cost: L1=0, L2=100, L3=300,
    L4=600, L5=1000, ... (each level costs a bit more than the last)."""
    return 50 * (lvl - 1) * lvl


def level_for_xp(xp):
    lvl = 1
    while xp >= xp_for_level(lvl + 1):
        lvl += 1
    return lvl


def _add_xp(profile, amount):
    g = _state(profile)
    before = g["level"]
    g["xp"] += amount
    g["level"] = level_for_xp(g["xp"])
    return {"xp": amount, "leveled": g["level"] > before, "level": g["level"]}


def on_correct(profile):
    """Right answer: build the streak and award streak-scaled XP.
    Returns a result dict for the tutor to show."""
    g = _state(profile)
    g["streak"] += 1
    g["best_streak"] = max(g["best_streak"], g["streak"])
    mult = min(1 + STREAK_STEP * (g["streak"] - 1), STREAK_CAP)
    res = _add_xp(profile, int(round(XP_CORRECT * mult)))
    res["streak"] = g["streak"]
    return res


def on_wrong(profile):
    """A miss breaks the streak (but never touches your XP or level)."""
    _state(profile)["streak"] = 0


def award(profile, amount):
    """Award a flat chunk of XP (concept cleared, code written, tier unlocked)."""
    return _add_xp(profile, amount)


# ── display helpers ─────────────────────────────────────────────────────────

def _bar(cur, total, width=20, full="█", empty="░"):
    total = max(total, 1)
    filled = max(0, min(width, int(width * cur / total)))
    return full * filled + empty * (width - filled)


def box_bar(box, maxbox=5):
    """A concept's mastery meter: ▰▰▰▱▱ for box 3/5."""
    box = max(0, min(maxbox, box))
    return "▰" * box + "▱" * (maxbox - box)


def correct_flair(res):
    """One-liner shown after a right answer: +XP, streak, any level-up."""
    bits = [f"+{res['xp']} XP"]
    if res.get("streak", 0) >= 2:
        bits.append(f"🔥 streak {res['streak']}")
    if res.get("leveled"):
        bits.append(f"⬆ LEVEL {res['level']}!")
    return "  " + "   ".join(bits)


def dashboard(profile, mastered, total, tier):
    """The banner shown when you start a session."""
    g = _state(profile)
    cur = xp_for_level(g["level"])
    nxt = xp_for_level(g["level"] + 1)
    into, span = g["xp"] - cur, nxt - cur
    bar = _bar(into, span)
    return (f"  LVL {g['level']}   [{bar}]  {into}/{span} to next level\n"
            f"  XP {g['xp']}   streak {g['streak']} (best {g['best_streak']})   "
            f"tier {tier} unlocked   mastered {mastered}/{total}")


def session_summary(profile, start_xp, start_level):
    """The wrap-up shown when you quit."""
    g = _state(profile)
    gained = g["xp"] - start_xp
    lines = [f"  +{gained} XP this session   (total {g['xp']})"]
    if g["level"] > start_level:
        lines.append(f"  ⬆ LEVEL UP:  {start_level} → {g['level']}")
    lines.append(f"  best streak this run: {g['best_streak']}")
    return "\n".join(lines)
