"""
code_check.py - runs YOUR code and checks if it actually works. No model.

tutor.py's quiz proves you UNDERSTAND a concept. This proves you can WRITE it.
And it answers "does it work?" the only reliable way: by RUNNING your code
against real test cases - not by asking a model to eyeball it. (Same reason
mastery.py does the scoring without the model: execution you can trust, kept
separate from opinion you can't.)

You write a function into my_code/<concept>.py. This imports it in a throwaway
subprocess, calls it with each test input, and compares what it returned to the
expected answer. All tests pass -> you cleared it. Any fail -> you see exactly
which input gave the wrong output, and fix it. The subprocess + timeout means a
crash or an infinite loop in your code can't take the tutor down with it.
"""
import os
import sys
import json
import subprocess

MY_CODE_DIR = os.path.join(os.environ.get("AXIOM_MASTERY_DIR", os.path.dirname(os.path.abspath(__file__))), "my_code")  # your answers (git-ignored)
TIMEOUT = 10          # seconds; a runaway while-loop gets cut off here


def _harness(key, func_name, tests):
    """Build a tiny throwaway script that imports the student's function and
    runs every test, printing one JSON line of results. Built by concatenating
    repr()'d values so there are no f-string/brace headaches."""
    lines = [
        "import sys, json",
        "sys.path.insert(0, " + repr(MY_CODE_DIR) + ")",
        "try:",
        "    import " + key + " as mod",
        "except Exception as e:",
        "    print(json.dumps({'fatal': 'your file has an error: ' + str(e)})); sys.exit()",
        "fn = getattr(mod, " + repr(func_name) + ", None)",
        "if fn is None:",
        "    print(json.dumps({'fatal': 'no function named " + func_name + " in your file'})); sys.exit()",
        "TESTS = " + repr(tests),
        "results = []",
        "for args, expected in TESTS:",
        "    try:",
        "        got = fn(*args)",
        "        results.append({'args': list(args), 'expected': expected, 'got': got, 'ok': got == expected})",
        "    except Exception as e:",
        "        results.append({'args': list(args), 'expected': expected, 'error': str(e), 'ok': False})",
        "print(json.dumps(results))",
    ]
    return "\n".join(lines)


def run_challenge(key, func_name, tests):
    """Run my_code/<key>.py's function against the tests.
    Returns (passed: bool, results: list). results is either a list of per-test
    dicts, or a one-item list holding an {'error': ...} message."""
    path = os.path.join(MY_CODE_DIR, key + ".py")
    if not os.path.exists(path):
        return False, [{"error": "no file yet at " + path + " - write your function there first"}]

    harness = _harness(key, func_name, tests)
    try:
        proc = subprocess.run([sys.executable, "-c", harness],
                              capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, [{"error": "timed out after %ss - maybe an infinite loop? check your condition" % TIMEOUT}]

    out = proc.stdout.strip()
    if not out:
        err = proc.stderr.strip()
        last = err.splitlines()[-1] if err else "your code didn't produce any result"
        return False, [{"error": last}]

    try:
        data = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return False, [{"error": "couldn't read the results - does your file print or ask for input? it shouldn't"}]

    if isinstance(data, dict) and "fatal" in data:
        return False, [{"error": data["fatal"]}]

    passed = all(r.get("ok") for r in data)
    return passed, data
