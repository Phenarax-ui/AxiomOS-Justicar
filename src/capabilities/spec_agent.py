"""
spec_agent.py -- turns a plain-language task into a structured build spec.

Where it sits in the stack:
    request -> spec_agent (this) -> human glance -> code_agent builds to spec

Generating a spec is an inert, read-only model call: it produces text, it
touches nothing. generate_spec() is therefore a PURE function -- no side
effects -- so code_agent can import and call it freely. The ledger logging
lives in the CLI path only, so the caller decides whether a run is recorded.

Run it:
    python -m capabilities.spec_agent "build a rate-limited retry wrapper with backoff"
    python -m capabilities.spec_agent --file task.txt
    python -m capabilities.spec_agent "..." --out specs/retry.json   # save for code_agent
    python -m capabilities.spec_agent "..." --json                   # raw JSON only
    python -m capabilities.spec_agent "..." --no-log                 # skip ledger entry
"""

import sys
import json
import argparse

from core import models
from core import config
from core.axiom_ledger import write_entry

# Shared with code_agent via core/config.py, so spec and build run on the SAME
# model (no eviction/reload between the two pipeline steps). Change it in one
# place — core/config.py — and both follow.
MODEL = config.CODER_MODEL


# A plain (non-f) string so the JSON braces below are literal -- no escaping.
SPEC_SYSTEM_PROMPT = """You are a software specification engine. You turn a short,
possibly-vague task description into a precise, structured build spec that a
coding model will implement against and that a human can review in under a minute.

You do NOT write the implementation. You define the contract.

Return ONLY a JSON object with exactly these keys:

{
  "title":        "<short name for the thing>",
  "summary":      "<1-2 sentences: what it does and why>",
  "inputs":       [{"name": "", "type": "", "description": ""}],
  "outputs":      [{"name": "", "type": "", "description": ""}],
  "interface":    ["<exact function/class signatures, e.g. 'def retry(fn, *, attempts: int = 3) -> Any'>"],
  "behavior":     ["<ordered steps describing what it does, one per item>"],
  "constraints":  ["<hard rules: performance, dependencies to avoid, side-effect limits>"],
  "edge_cases":   ["<inputs or conditions the implementation must handle>"],
  "acceptance_tests": [
    {"description": "<what this checks>", "example_input": "<concrete input>", "expected_output": "<concrete expected result>"}
  ],
  "dependencies": ["<stdlib or third-party modules it should use, or 'none'>"],
  "open_questions": ["<anything ambiguous in the task a human should decide before building>"]
}

Rules:
- Prefer the standard library. Only list a third-party dependency if genuinely needed.
- Make acceptance_tests CONCRETE and executable where possible -- real inputs, real
  expected outputs -- because they become the pass/fail targets for the build step.
- Cover the obvious failure modes in edge_cases (empty input, bad type, boundary values).
- If the task is underspecified, DO NOT invent requirements silently. Make a reasonable
  assumption, build the spec around it, and record the assumption in open_questions.
- Keep it tight. A spec is read by a human; every line should earn its place.
- Output valid JSON only. No prose, no markdown, no code fences."""


def generate_spec(task: str, *, model: str = MODEL) -> dict:
    """Produce a structured spec dict for a plain-language task.

    PURE: no logging, no file writes, no network beyond the model call.
    Importable by code_agent:  from capabilities.spec_agent import generate_spec
    """
    task = task.strip()
    if not task:
        raise ValueError("spec_agent: empty task")

    messages = [
        {"role": "system", "content": SPEC_SYSTEM_PROMPT},
        {"role": "user", "content": f"TASK:\n{task}\n\nProduce the spec as JSON."},
    ]

    spec = models.chat_json(messages, model, options={"temperature": 0})

    if not isinstance(spec, dict):
        raise models.ModelError(
            f"spec_agent: expected a JSON object, got {type(spec).__name__}"
        )

    spec.setdefault("task", task)
    return spec


# ---------------------------------------------------------------------------
# Pretty-printing for human review
# ---------------------------------------------------------------------------

def _line(label, value):
    print(f"  {label}: {value}")


def print_spec(spec: dict) -> None:
    print("=" * 70)
    print(f"SPEC: {spec.get('title', '(untitled)')}")
    print("=" * 70)
    print(spec.get("summary", ""))

    def section(name, key, render):
        items = spec.get(key) or []
        if not items:
            return
        print(f"\n{name}:")
        for it in items:
            render(it)

    section("INPUTS", "inputs",
            lambda d: _line("-", f"{d.get('name','?')} ({d.get('type','?')}) -- {d.get('description','')}"))
    section("OUTPUTS", "outputs",
            lambda d: _line("-", f"{d.get('name','?')} ({d.get('type','?')}) -- {d.get('description','')}"))
    section("INTERFACE", "interface", lambda s: print(f"    {s}"))
    section("BEHAVIOR", "behavior", lambda s: print(f"    - {s}"))
    section("CONSTRAINTS", "constraints", lambda s: print(f"    - {s}"))
    section("EDGE CASES", "edge_cases", lambda s: print(f"    - {s}"))

    tests = spec.get("acceptance_tests") or []
    if tests:
        print("\nACCEPTANCE TESTS:")
        for i, t in enumerate(tests, 1):
            print(f"    {i}. {t.get('description','')}")
            if t.get("example_input") is not None:
                print(f"       in:  {t.get('example_input')}")
            if t.get("expected_output") is not None:
                print(f"       out: {t.get('expected_output')}")

    section("DEPENDENCIES", "dependencies", lambda s: print(f"    - {s}"))

    oq = spec.get("open_questions") or []
    if oq:
        print("\n⚠  OPEN QUESTIONS (resolve before building):")
        for q in oq:
            print(f"    - {q}")
    print("=" * 70)


def _log_spec(task: str, spec: dict) -> None:
    """Record that a spec was generated, to the append-only ledger.
    Non-fatal: a ledger hiccup must not lose the spec the user just made."""
    try:
        write_entry(
            action=f"generate_spec: {spec.get('title', task[:50])}",
            requester="spec_agent",
            decision="generated",
            reasoning=(
                f"{len(spec.get('acceptance_tests') or [])} acceptance tests, "
                f"{len(spec.get('open_questions') or [])} open questions"
            ),
        )
    except Exception as e:
        print(f"[spec_agent] warning: ledger log failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate a structured build spec from a task.")
    ap.add_argument("task", nargs="?", help="the task description")
    ap.add_argument("--file", help="read the task from a file instead")
    ap.add_argument("--model", default=MODEL, help=f"ollama model tag (default {MODEL})")
    ap.add_argument("--out", help="write the spec JSON to this path (specs/ is the usual home)")
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    ap.add_argument("--no-log", action="store_true", help="do not record this spec in the ledger")
    args = ap.parse_args(argv)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            task = f.read()
    elif args.task:
        task = args.task
    else:
        ap.error("provide a task string or --file")

    try:
        spec = generate_spec(task, model=args.model)
    except models.ModelError as e:
        print(f"spec_agent error: {e}", file=sys.stderr)
        return 1

    if not args.no_log:
        _log_spec(task, spec)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
        print(f"spec written to {args.out}")

    if args.json:
        print(json.dumps(spec, indent=2))
    else:
        print_spec(spec)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
