"""
code_agent.py - a local agent that writes and tests its own code.

Give it a task. It writes Python, runs it in a subprocess, and if it fails,
feeds the error back to the model and tries again, up to a few attempts.

Every piece of generated code must now pass a constitutional review BEFORE it
is allowed to run. The review is two layers, same shape as axiom_gate:
    1. a deterministic scan that hard-denies unambiguous violations
       (network egress, dynamic exec, secret exfiltration)
    2. a model layer that judges the ambiguous cases against the constitution
It fails closed: if the review errors or can't decide, the code does NOT run.

All model calls go through core.models (no `ollama` library dependency).

Run:
    python3 code_agent.py "write a function that checks if a string is a palindrome, with 3 test cases"

Flags:
    --max-tries N     how many fix attempts before giving up (default 4)
    --save FILE       save the final working code to FILE
    --spec-first      generate a structured spec first, then build to it
    --no-review       DANGER: skip the constitutional review (for debugging only)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import os
from core import constitution
from core import models
from core import config
from capabilities.spec_agent import generate_spec, print_spec

MODEL = config.CODER_MODEL   # single source of truth (core/config.py)

# The reviewer. Defaults to the SAME model that is already loaded, so you don't
# pay a model reload on every attempt (you run OLLAMA_MAX_LOADED_MODELS=1).
# Point this at "qwen3:4b" if you'd rather use your gate model for the judgment
# and can accept the reload cost -- if you do, pass think=False to the chat call.
REVIEW_MODEL = MODEL


SYSTEM_PROMPT = (
    "You are a careful Python programmer. When given a task, respond with a "
    "single Python code block only - no explanation before or after. The code "
    "must run standalone with `python3 file.py` and print clear output showing "
    "it works, including any test cases. Use only the Python standard library "
    "unless the task explicitly names another package."
)


REVIEW_SYSTEM_PROMPT = (
    "You are the constitutional reviewer for a local-first AI system. You are "
    "given a block of Python the system wrote and is about to run on the user's "
    "own machine. Judge ONLY whether running it would violate the constitution "
    "below. Benign local code (math, string processing, local file work in the "
    "working directory, tests, data structures) is ALLOWED. Respond with a "
    'single JSON object and nothing else: {"allowed": true|false, "reasoning": '
    '"<one sentence>"}.\n\n' + constitution.ARTICLES
)

# Deterministic hard-deny patterns: unambiguous constitutional violations.
_HARD_DENY = [
    (r"\bimport\s+socket\b|\bsocket\.socket\b", "opens a raw network socket"),
    (r"\b(urllib|requests|http\.client|httpx|aiohttp)\b", "makes network/HTTP requests"),
    (r"\b(ftplib|smtplib|telnetlib|poplib|imaplib)\b", "opens a network/mail connection"),
    (r"\burlopen\b|\.connect\(\s*\(", "opens a network connection"),
    (r"\beval\(|\bexec\(|\b__import__\(|\bcompile\(", "executes dynamically-constructed code"),
]

# Patterns that are suspicious but context-dependent -> send to the model layer.
_NEEDS_REVIEW = [
    r"\bos\.system\b|\bsubprocess\b|\bos\.popen\b|\bpty\b",
    r"\bos\.environ\b|\bgetenv\b",
    r"\bshutil\.rmtree\b|\bos\.remove\b|\bos\.unlink\b|\bos\.rmdir\b",
    r"\bopen\(\s*['\"]\s*/|['\"]\.\.\/",   # writing to an absolute path or parent dir
    r"\bos\.chmod\b|\bos\.chown\b|crontab|systemctl",
]


def _deterministic_code_scan(code):
    """Return ('deny'|'review'|'allow', reason)."""
    for pattern, reason in _HARD_DENY:
        if re.search(pattern, code):
            return "deny", reason
    for pattern in _NEEDS_REVIEW:
        if re.search(pattern, code):
            return "review", "contains operations that need judgment"
    return "allow", "no risky operations detected"


def constitutional_code_review(code, model=REVIEW_MODEL):
    """
    Judge generated code against the constitution before it runs.
    Returns (allowed: bool, reasoning: str). Fails closed on any error.

    `model` lets a caller run the review on whatever model it already has
    loaded (e.g. agent_tools.py passes its own MODEL) to avoid a reload.
    """
    verdict, reason = _deterministic_code_scan(code)

    if verdict == "deny":
        return False, f"Deterministic block: {reason} (Article 2.3 / 2.2)."
    if verdict == "allow":
        return True, "Passed deterministic scan; no risky operations."

    # Ambiguous -> ask the model layer. chat_json constrains the reply to JSON,
    # parses it, and raises ModelError on any failure (which we fail closed on).
    try:
        data = models.chat_json(
            [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": f"Code to review:\n\n{code}"},
            ],
            model,
            options={"temperature": 0},
        )
        allowed = bool(data["allowed"])
        reasoning = str(data.get("reasoning", "")).strip() or "no reasoning given"
        return allowed, reasoning
    except Exception as e:
        # Fail closed: if the reviewer can't reach a verdict, deny execution.
        return False, f"Review error, failing closed: {e}"


def extract_code(text):
    """Pull the first ```python ... ``` or ``` ... ``` block out of a response."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def ask_model(messages):
    return models.chat(messages, MODEL)


def _spec_to_brief(spec, task):
    """Fold a structured spec into a concrete build brief for the coder model.
    The acceptance tests are stated as hard targets so write_and_fix's run loop
    has something real to verify against."""
    lines = [f"Build this. Task: {task}", ""]
    if spec.get("interface"):
        lines.append("Required interface (match these signatures exactly):")
        lines += [f"  {s}" for s in spec["interface"]]
        lines.append("")
    if spec.get("constraints"):
        lines.append("Constraints:")
        lines += [f"  - {c}" for c in spec["constraints"]]
        lines.append("")
    if spec.get("edge_cases"):
        lines.append("Must handle these edge cases:")
        lines += [f"  - {e}" for e in spec["edge_cases"]]
        lines.append("")
    tests = spec.get("acceptance_tests") or []
    if tests:
        lines.append("Must pass these acceptance tests - include them as runnable "
                     "assertions in your output:")
        for t in tests:
            desc = t.get("description", "")
            ei, eo = t.get("example_input"), t.get("expected_output")
            line = f"  - {desc}"
            if ei is not None or eo is not None:
                line += f" (input: {ei} -> expected: {eo})"
            lines.append(line)
    return "\n".join(lines)


def run_code(code):
    """Run code in a temp file, return (success, output)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=15
        )
        ok = result.returncode == 0
        output = result.stdout if ok else result.stdout + result.stderr
        return ok, output
    except subprocess.TimeoutExpired:
        return False, "Execution timed out after 15 seconds (possible infinite loop)."
    finally:
        os.unlink(path)


def write_and_fix(task, max_tries=4, review=True, spec=None):
    # If a spec was generated, build to it instead of the bare task.
    user_task = _spec_to_brief(spec, task) if spec else task

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_task},
    ]

    for attempt in range(1, max_tries + 1):
        print(f"\n--- Attempt {attempt}/{max_tries} ---")
        reply = ask_model(messages)
        code = extract_code(reply)

        # --- Constitutional review: gate the code BEFORE it runs. ---
        if review:
            print("Reviewing code against the constitution...")
            allowed, reasoning = constitutional_code_review(code)
            if not allowed:
                print(f"BLOCKED BY CONSTITUTION: {reasoning}")
                messages.append({"role": "assistant", "content": reply})
                messages.append({
                    "role": "user",
                    "content": (
                        "That code was blocked by the constitutional review for "
                        f"this reason: {reasoning}\n\n"
                        "Rewrite it so it does the task using only safe, local, "
                        "standard-library operations - no network access, no "
                        "dynamic code execution, no reading or transmitting "
                        "secrets, no destructive filesystem operations. Respond "
                        "with a single corrected Python code block only."
                    ),
                })
                continue
            print(f"Constitution: allowed ({reasoning})")

        print("Running code...")
        ok, output = run_code(code)

        if ok:
            print("Success. Output:\n")
            print(output)
            return code, output

        print("Failed. Output/error:\n")
        print(output)
        messages.append({"role": "assistant", "content": reply})
        messages.append({
            "role": "user",
            "content": (
                f"That code failed when run. Here is the error output:\n\n{output}\n\n"
                "Fix the code and respond again with a single corrected Python "
                "code block only."
            ),
        })

    print(f"\nGave up after {max_tries} attempts.")
    return None, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task", help="Description of what the code should do")
    parser.add_argument("--max-tries", type=int, default=4)
    parser.add_argument("--save", help="File to save the final working code to")
    parser.add_argument("--spec-first", action="store_true",
                        help="generate a structured spec first, then build to it")
    parser.add_argument("--no-review", action="store_true",
                        help="DANGER: skip the constitutional review (debugging only)")
    args = parser.parse_args()

    # --- Optional: spec the task before building (the cheap human checkpoint). ---
    spec = None
    if args.spec_first:
        print("Generating spec first...\n")
        spec = generate_spec(args.task)
        print_spec(spec)
        if sys.stdin.isatty():
            if input("\nBuild to this spec? (y/n): ").strip().lower() != "y":
                print("Stopped. No code generated.")
                sys.exit(0)

    code, output = write_and_fix(args.task, args.max_tries,
                                 review=not args.no_review, spec=spec)

    if code and args.save:
        with open(args.save, "w") as f:
            f.write(code)
        print(f"\nSaved working code to {args.save}")
