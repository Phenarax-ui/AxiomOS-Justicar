"""
agent_tools.py - a local agent with a small toolset it can call.

The model is given a task and a list of tools. It replies with a tool call
(as JSON) or a final answer. The loop executes the tool, feeds the result
back, and repeats until the model says it's done or a step limit is hit.

Run:
    python3 agent_tools.py "read notes.txt, summarize it, and save the summary to summary.txt"

Safety notes:
- run_python is now gated: before any model-written code executes, it goes
  through constitutional_code_review (deterministic scan + model judgment,
  fail-closed). Code that violates the constitution is refused, not run.
- review_code is a tool the agent can call to check code against the
  constitution without running it.
- run_shell still asks for your y/n confirmation before executing.
- web_search makes network requests (DuckDuckGo). It is left ungated here on
  purpose; fully routing write_file / web_search / run_shell through
  axiom_gate.evaluate_action is the next step.
"""
import argparse
import json
import re
import subprocess
import sys
import os
from core import models 
from duckduckgo_search import DDGS

# Shared governance: one reviewer logic across both agents.
from capabilities.code_agent import constitutional_code_review

MODEL = "qwen3-coder:30b"
MAX_STEPS = 10

# ---------- Tool implementations ----------

def tool_read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"ERROR: {e}"


def tool_write_file(path, content):
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"ERROR: {e}"


def tool_list_dir(path="."):
    try:
        return "\n".join(sorted(os.listdir(path)))
    except Exception as e:
        return f"ERROR: {e}"


def tool_run_python(code):
    # Gate the code against the constitution BEFORE running it. Fail closed.
    allowed, reasoning = constitutional_code_review(code, model=MODEL)
    if not allowed:
        return f"BLOCKED BY CONSTITUTION: {reasoning}"
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15
        )
        return (result.stdout + result.stderr) or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timed out after 15 seconds"


def tool_review_code(code):
    """Check code against the constitution without running it."""
    allowed, reasoning = constitutional_code_review(code, model=MODEL)
    return f"{'ALLOWED' if allowed else 'DENIED'}: {reasoning}"


def tool_web_search(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return "\n".join(f"- {r['title']}: {r['href']}" for r in results) or "No results."
    except Exception as e:
        return f"ERROR: {e}"


def tool_run_shell(command):
    print(f"\n[run_shell wants to execute]: {command}")
    confirm = input("Allow this? (y/n): ").strip().lower()
    if confirm != "y":
        return "User declined to run this command."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return (result.stdout + result.stderr) or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timed out after 30 seconds"


TOOLS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_dir": tool_list_dir,
    "run_python": tool_run_python,
    "review_code": tool_review_code,
    "web_search": tool_web_search,
    "run_shell": tool_run_shell,
}

TOOL_DESCRIPTIONS = """
Available tools - call one per turn by replying with ONLY a JSON object, nothing else:

{"tool": "read_file", "args": {"path": "notes.txt"}}
{"tool": "write_file", "args": {"path": "out.txt", "content": "..."}}
{"tool": "list_dir", "args": {"path": "."}}
{"tool": "run_python", "args": {"code": "print(1+1)"}}
{"tool": "review_code", "args": {"code": "..."}}
{"tool": "web_search", "args": {"query": "..."}}
{"tool": "run_shell", "args": {"command": "..."}}

Note: run_python is automatically reviewed against the constitution before it
runs. If it returns "BLOCKED BY CONSTITUTION", rewrite the code to use only
safe, local, standard-library operations - no network access, no dynamic code
execution, no secret reads, no destructive filesystem operations. You can call
review_code first to check code without running it.

When the task is fully complete, reply with ONLY:
{"done": true, "summary": "<what you accomplished>"}

Reply with exactly one JSON object per turn. No explanation, no markdown fences.
"""


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def run_agent(task, max_steps=MAX_STEPS):
    messages = [
        {"role": "system", "content": (
            "You are a local agent that solves tasks by calling tools step by step.\n"
            + TOOL_DESCRIPTIONS
        )},
        {"role": "user", "content": task},
    ]

    for step in range(1, max_steps + 1):
        print(f"\n--- Step {step}/{max_steps} ---")
        reply = models.chat(messages, MODEL)
        parsed = extract_json(reply)

        if not parsed:
            print(f"[model did not return valid JSON, stopping]\n{reply}")
            break

        if parsed.get("done"):
            print(f"Done: {parsed.get('summary', '(no summary given)')}")
            return

        tool_name = parsed.get("tool")
        args = parsed.get("args", {})
        fn = TOOLS.get(tool_name)

        if not fn:
            result = f"ERROR: unknown tool '{tool_name}'"
        else:
            print(f"[calling {tool_name}] {args}")
            result = fn(**args)

        print(f"[result] {str(result)[:500]}")

        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": f"Tool result:\n{result}"})

    else:
        print(f"\nStopped after {max_steps} steps without finishing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args()
    run_agent(args.task, args.max_steps)
