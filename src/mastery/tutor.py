#!/usr/bin/env python3
"""
tutor.py - the interactive loop. The ONLY file that talks to the model
(qwen3-coder:30b on IRWIN, via Ollama).

Each round:
  1. mastery.py picks your weakest concept (from unlocked tiers only).
  2. The model writes ONE question about it, grounded in the concept brief.
  3. You answer.
  4. The model grades YOUR answer against the brief and returns a verdict.
  5. Once you've shown you UNDERSTAND it, a code challenge makes you WRITE it -
     code_check.py RUNS your code to decide.
  6. mastery.py updates your profile; game.py awards XP / streak / levels.

Understanding and producing are different skills, so the quiz proves the first
and the code challenge proves the second - and "does it work?" is answered by
running your code, not by asking the model. game.py sits on top of all of it to
make the grind feel like levelling up instead of homework.

Run on IRWIN (where the model lives):
    python3 tutor.py            # drills python by default
    python3 tutor.py python     # same
"""
import os
import sys

# Let this file find the shared core/ package whether you run it from inside
# mastery/ (python3 tutor.py) or from the project root (python3 mastery/tutor.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from core import config, models               # one model tag + one Ollama client for everything

import mastery
import game
import code_check
from curriculum import CONCEPTS
from code_tasks import CODE_TASKS

MODEL = config.CODER_MODEL                    # set in core/config.py


def ask_model(prompt):
    """Send one prompt to the model and return the text reply."""
    return models.generate(prompt, MODEL, timeout=300)


def make_question(concept):
    """Ask the model to write one question, grounded in the concept brief so
    it can't drift off into something the curriculum never taught."""
    prompt = (
        f"You are a Python tutor. The topic is: {concept['label']}.\n"
        f"Ground truth you must stay within:\n{concept['brief']}\n"
        f"Canonical syntax: {concept['syntax_anchor']}\n\n"
        "Write ONE short question that checks whether the student really "
        "understands this. Prefer asking them to explain why, or to predict "
        "what a snippet prints, over asking them to recite a definition.\n"
        "Output only the question. No preamble, no answer."
    )
    return ask_model(prompt)


def grade_answer(concept, question, answer):
    """Have the model grade the student's answer against the brief.
    Returns (verdict, feedback) with verdict in CORRECT / PARTIAL / WRONG."""
    prompt = (
        f"You are grading a student's answer about {concept['label']}.\n"
        f"Ground truth:\n{concept['brief']}\n\n"
        f"Question asked: {question}\n"
        f"Student's answer: {answer}\n\n"
        "Grade it. Respond in EXACTLY this format, nothing before it:\n"
        "VERDICT: CORRECT | PARTIAL | WRONG\n"
        "FEEDBACK: one or two sentences. Say what was right or wrong, and "
        "give the correct answer if they missed it."
    )
    reply = ask_model(prompt)

    verdict = "PARTIAL"
    feedback = reply
    for line in reply.splitlines():
        s = line.strip()
        up = s.upper()
        if up.startswith("VERDICT:"):
            v = up.split(":", 1)[1]
            if "CORRECT" in v:
                verdict = "CORRECT"
            elif "WRONG" in v:
                verdict = "WRONG"
            else:
                verdict = "PARTIAL"
        elif up.startswith("FEEDBACK:"):
            feedback = s.split(":", 1)[1].strip()
    return verdict, feedback


MARK = {"CORRECT": "✓", "PARTIAL": "~", "WRONG": "✗"}

REQUIRED_CORRECT = 3
MAX_ATTEMPTS = 6


def teach(concept):
    """Explain a concept BEFORE testing it (the curriculum brief - the same
    ground truth the grader checks against)."""
    print(f"\n  {concept['brief']}")
    print(f"  syntax: {concept['syntax_anchor']}\n")


def explain_syntax(concept):
    """Have the model walk through the example line by line on first exposure.
    Skipped quietly if the model can't be reached."""
    prompt = (
        f"You are teaching a beginner the Python concept: {concept['label']}.\n"
        f"Ground truth you must stay consistent with:\n{concept['brief']}\n\n"
        f"The canonical example is:\n{concept['syntax_anchor']}\n\n"
        "Walk a beginner through this example part by part. For each piece of "
        "syntax, give one short line: what it does and why it's there. "
        "A few lines total. No preamble, no restating the whole concept."
    )
    try:
        text = ask_model(prompt)
    except models.ModelError:
        return
    print("  how it works:")
    for line in text.splitlines():
        if line.strip():
            print(f"    {line.strip()}")
    print()


def _show_results(results):
    """Print per-test outcomes from code_check so a miss shows exactly which
    input gave the wrong output."""
    for r in results:
        if "args" not in r:
            print(f"    ✗ {r.get('error', 'unknown error')}")
            continue
        args = ", ".join(repr(a) for a in r.get("args", []))
        if r.get("ok"):
            print(f"    ✓ ({args}) -> {r['got']!r}")
        elif "error" in r:
            print(f"    ✗ ({args}) -> crashed: {r['error']}")
        else:
            print(f"    ✗ ({args}) -> got {r.get('got')!r}, expected {r['expected']!r}")


def _explain_failure(concept, results):
    """On a failed code challenge, let the model explain WHY (its strength)
    without letting it decide pass/fail (code_check already ran the code)."""
    wrong = [r for r in results if not r.get("ok")]
    if not wrong:
        return
    summary = "; ".join(
        f"input ({', '.join(repr(a) for a in r.get('args', []))}) gave "
        + (f"error {r['error']}" if "error" in r else f"{r.get('got')!r} but should be {r['expected']!r}")
        for r in wrong[:3]
    )
    prompt = (
        f"A beginner is writing Python for: {concept['label']}.\n"
        f"Concept: {concept['brief']}\n\n"
        f"Their function failed these tests: {summary}\n\n"
        "In ONE or TWO sentences, hint at what's likely wrong and how to think "
        "about the fix. Do NOT write the solution for them. No preamble."
    )
    try:
        hint = ask_model(prompt)
    except models.ModelError:
        return
    print(f"  hint: {hint}\n")


def code_challenge(concept, key):
    """After the quiz proves you UNDERSTAND it, this proves you can WRITE it.
    Returns True if your code passes the tests (or there's no challenge yet)."""
    task = CODE_TASKS.get(key)
    if not task:
        return True

    os.makedirs(code_check.MY_CODE_DIR, exist_ok=True)
    path = os.path.join(code_check.MY_CODE_DIR, key + ".py")

    print("\n── Now WRITE it ──")
    print(task["task"])
    print(f"\n  → put your function in:  {path}")
    print("  → write ONLY the function (don't call it - the tutor calls it)")
    print("  → save it, then press Enter here to run the tests.  ('skip' to skip)\n")

    while True:
        cmd = input("[Enter to run / 'skip']> ").strip().lower()
        if cmd in ("skip", "quit", "exit"):
            print("(skipped the code challenge)\n")
            return False

        passed, results = code_check.run_challenge(key, task["func"], task["tests"])
        if passed:
            print("\n  ✓✓ all tests passed - you didn't just understand it, you WROTE it.\n")
            return True

        print()
        _show_results(results)
        print()
        _explain_failure(concept, results)
        print("Fix your function, save, and press Enter to run it again.  ('skip' to skip)\n")


def drill(profile, key):
    """Teach (if new), quiz to REQUIRED_CORRECT reps, then a code challenge to
    prove you can write it. Clears the concept (box up + XP) only when both are
    done. Returns 'quit' if you asked to stop."""
    concept = CONCEPTS[key]
    entry = profile.get(key, {})
    box = entry.get("box", 0)
    first_time = entry.get("seen", 0) == 0

    print(f"── {concept['label']}  {game.box_bar(box)}  (box {box}/{mastery.MAX_BOX}) " + "─" * 6)
    if first_time:
        teach(concept)
        explain_syntax(concept)

    got = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            question = make_question(concept)
        except models.ModelError as e:
            print(f"\n[could not reach the model: {e}]")
            print("Is Ollama running on this machine? Try: ollama ps")
            return "quit"

        print(f"\n[rep {got}/{REQUIRED_CORRECT} — question {attempt}/{MAX_ATTEMPTS}]")
        print(f"{question}\n")
        answer = input("your answer> ").strip()
        if not answer:
            print("(skipped — moving on, no change)\n")
            return None
        if answer.lower() in ("quit", "exit"):
            return "quit"

        verdict, feedback = grade_answer(concept, question, answer)
        print(f"\n{MARK[verdict]} {verdict}")
        print(f"{feedback}")

        mastery.note_attempt(profile, key, verdict)
        if verdict == "CORRECT":
            res = game.on_correct(profile)
            print(game.correct_flair(res))
        else:
            game.on_wrong(profile)
        print()
        mastery.save_profile(profile)

        if verdict == "CORRECT":
            got += 1
            if got >= REQUIRED_CORRECT:
                # Understanding proven. Now prove you can WRITE it.
                if code_challenge(concept, key):
                    mastery.pass_session(profile, key)
                    gained = game.XP_PASS + (game.XP_CODE if key in CODE_TASKS else 0)
                    r = game.award(profile, gained)
                    mastery.save_profile(profile)
                    newbox = profile[key]["box"]
                    print(f"✓✓ cleared {concept['label']}   {game.box_bar(newbox)}   +{gained} XP"
                          + (f"   ⬆ LEVEL {r['level']}!" if r["leveled"] else "") + "\n")
                else:
                    print(f"You understand {concept['label']} — come back and WRITE it "
                          "to fully clear it. (No box change this round.)\n")
                return None
        else:
            print("Same idea, another angle — here's the concept again:")
            teach(concept)

    mastery.fail_session(profile, key)
    mastery.save_profile(profile)
    print(f"got {got}/{REQUIRED_CORRECT} correct this round — we'll come back to it.\n")
    return None


def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else "python"
    profile = mastery.load_profile()

    start = game._state(profile)
    start_xp, start_level = start["xp"], start["level"]
    tier = mastery.current_level(profile, domain)
    done, total = mastery.progress(profile, domain)

    print(f"\nMastery tutor — drilling '{domain}'")
    print(game.dashboard(profile, done, total, tier))
    print("\nAnswer each question. Ctrl+C any time to save and quit.\n")

    try:
        while True:
            key = mastery.pick_concept(profile, domain)
            if key is None:
                print(f"No concepts found for domain '{domain}'.")
                break
            if drill(profile, key) == "quit":
                break

            new_tier = mastery.current_level(profile, domain)
            if new_tier > tier:
                r = game.award(profile, game.XP_TIER_UNLOCK)
                mastery.save_profile(profile)
                print("\n★ ─────────────────────────── ★")
                print(f"   TIER {new_tier} UNLOCKED!   +{game.XP_TIER_UNLOCK} XP"
                      + (f"   ⬆ LEVEL {r['level']}!" if r["leveled"] else ""))
                print("★ ─────────────────────────── ★\n")
                tier = new_tier

            done, total = mastery.progress(profile, domain)
            print(f"progress: {done}/{total} mastered\n")
    except KeyboardInterrupt:
        pass

    mastery.save_profile(profile)
    print("\n── session over ──")
    print(game.session_summary(profile, start_xp, start_level))
    print("\nsaved. come back any time.")


if __name__ == "__main__":
    main()
