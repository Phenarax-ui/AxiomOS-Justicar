"""
axiom_agent.py — a governed, tool-using agent.

A natural-language agent that acts through tools (native Ollama tool calling).
Every tool call is routed through the constitutional gate before it runs and
logged to the tamper-evident ledger — there is no unobserved action. The agent
has durable memory (recall / remember / graph_query) and runs generated code in
a sandbox.

Setup:
    # a sandbox for generated code (optional but recommended)
    sudo apt install firejail
    # a local model with tool-calling support, and a small gate model
    ollama pull gpt-oss:20b && ollama pull qwen3:4b
Run:
    python3 axiom_agent.py
"""
import os
import re
import sys
import json
import shutil
import tempfile
import subprocess

import requests
import ollama

import memory
from axiom_gate import evaluate_action

OLLAMA_CHAT = "http://localhost:11434/api/chat"
MODEL       = "gpt-oss:20b"     # any local model with tool-calling support
NUM_CTX     = 16384
REQUESTER   = "agent"
GEN_TIMEOUT = 600

# sandboxed-execution settings (run_python + write_and_test)
CODER_MODEL      = MODEL
CODE_MAX_TRIES   = 4
CODE_TIMEOUT     = 15
SANDBOX_REQUIRED = True

SYSTEM_PROMPT = """You are an agent running inside AxiomOS. You act through tools:
read_file, write_file, list_dir, run_python (sandboxed), run_shell, write_and_test
(writes Python, runs it sandboxed, auto-fixes), and a memory — recall (search what
you already know), remember (store a durable fact, with edges linking entities),
and graph_query (traverse the knowledge graph).

Every tool call is checked by the constitutional gate before it runs; if one is
blocked you will be told which principle it violated — adapt and find a safe path.
When asked what you know about something, call recall first before acting. Explain
your results plainly."""

CODER_SYSTEM = (
    "You are a careful Python programmer. Given a task, respond with a single Python "
    "code block only — no prose. The code must run standalone with python3 and print "
    "output showing it works, including test cases. Standard library only unless the "
    "task names another package."
)


# --------------------------------------------------------------------------
# Sandbox (shared by run_python and write_and_test)
# --------------------------------------------------------------------------
def _run_in_sandbox(code):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        fj = shutil.which("firejail")
        if fj:
            cmd = [fj, "--quiet", "--net=none", "--private", sys.executable, path]
        elif SANDBOX_REQUIRED:
            return False, ("SANDBOX UNAVAILABLE: firejail not installed, refusing to run "
                           "generated code. Install it: sudo apt install firejail")
        else:
            cmd = [sys.executable, path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CODE_TIMEOUT)
        ok = r.returncode == 0
        return ok, (r.stdout if ok else r.stdout + r.stderr) or "(no output)"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {CODE_TIMEOUT}s (possible infinite loop)"
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
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
        return f"wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"ERROR: {e}"


def tool_list_dir(path="."):
    try:
        return "\n".join(sorted(os.listdir(path)))
    except Exception as e:
        return f"ERROR: {e}"


def tool_run_python(code):
    ok, out = _run_in_sandbox(code)
    return out


def tool_run_shell(command):
    try:
        out = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr)[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timed out after 30 seconds"


def _extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def tool_write_and_test(task):
    msgs = [{"role": "system", "content": CODER_SYSTEM},
            {"role": "user",   "content": task}]
    code, out = "", ""
    for attempt in range(1, CODE_MAX_TRIES + 1):
        reply = ollama.chat(model=CODER_MODEL, messages=msgs, think=False)["message"]["content"]
        code = _extract_code(reply)
        ok, out = _run_in_sandbox(code)
        if ok:
            return json.dumps({"status": "passed", "attempts": attempt, "code": code, "output": out})
        msgs.append({"role": "assistant", "content": reply})
        msgs.append({"role": "user",
                     "content": f"That failed when run:\n\n{out}\n\nFix it; single code block only."})
    return json.dumps({"status": "failed", "attempts": CODE_MAX_TRIES, "code": code, "output": out})


def tool_remember(content, edges=None):
    return memory.remember(content, edges=edges, source="agent")


def tool_recall(query):
    return memory.recall(query)


def tool_graph_query(node, relation=None, depth=1):
    return memory.graph_query(node, relation=relation, depth=depth)


TOOLS = {
    "read_file":      tool_read_file,
    "write_file":     tool_write_file,
    "list_dir":       tool_list_dir,
    "run_python":     tool_run_python,
    "run_shell":      tool_run_shell,
    "write_and_test": tool_write_and_test,
    "remember":       tool_remember,
    "recall":         tool_recall,
    "graph_query":    tool_graph_query,
}

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a UTF-8 text file (first 8000 chars).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Write text to a file, overwriting it.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "List the entries in a directory.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "run_python", "description": "Run a Python snippet in a network-isolated sandbox.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                       "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "run_shell", "description": "Run a shell command; returns combined stdout/stderr.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "write_and_test",
        "description": "Write Python for a task, run it sandboxed, auto-fix on failure.",
        "parameters": {"type": "object", "properties": {"task": {"type": "string"}},
                       "required": ["task"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": ("Store a durable fact in memory, with optional edges linking entities. "
                        "Relations: relates_to, part_of, depends_on, caused_by, instance_of, "
                        "located_in, similar_to, note."),
        "parameters": {"type": "object",
                       "properties": {
                           "content": {"type": "string"},
                           "edges": {"type": "array",
                                     "items": {"type": "object",
                                               "properties": {"src": {"type": "string"},
                                                              "relation": {"type": "string"},
                                                              "dst": {"type": "string"}}}}},
                       "required": ["content"]}}},
    {"type": "function", "function": {
        "name": "recall", "description": "Search memory (facts and relations) for a query.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "graph_query", "description": "Traverse the knowledge graph from a node.",
        "parameters": {"type": "object",
                       "properties": {"node": {"type": "string"},
                                      "relation": {"type": "string"},
                                      "depth": {"type": "integer"}},
                       "required": ["node"]}}},
]


# --------------------------------------------------------------------------
# Native tool calling + gated execution
# --------------------------------------------------------------------------
def _chat(messages):
    payload = {"model": MODEL, "messages": messages, "tools": TOOL_SPECS,
               "stream": False, "options": {"num_ctx": NUM_CTX}}
    r = requests.post(OLLAMA_CHAT, json=payload, timeout=GEN_TIMEOUT)
    r.raise_for_status()
    return r.json()["message"]


def _run_tool(name, args):
    fn = TOOLS.get(name)
    if fn is None:
        return f"error: unknown tool '{name}'"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"error running {name}: {e}"


def handle_turn(messages):
    while True:
        msg = _chat(messages)
        messages.append(msg)

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return (msg.get("content") or msg.get("thinking", "")), messages

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"].get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}

            verdict  = evaluate_action({"tool": name, "args": args}, REQUESTER)
            decision = verdict["decision"]

            if decision == "allowed":
                result = _run_tool(name, args)
            elif decision == "pending_confirmation":
                ans = input(f"\n[gate] confirm {name}({args})?\n"
                            f"       {verdict.get('reasoning')}\n       [y/N] ")
                result = _run_tool(name, args) if ans.strip().lower() == "y" \
                         else "blocked by human: confirmation denied"
            else:
                result = (f"BLOCKED by the constitutional gate "
                          f"({verdict.get('axiom_triggered')}): {verdict.get('reasoning')}")

            print(f"  · {name}({args}) -> {decision}")
            messages.append({"role": "tool", "tool_name": name, "content": result})


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("AxiomOS agent — every tool call passes the constitutional gate. Ctrl-C to quit.\n")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break
        if not user:
            continue
        messages.append({"role": "user", "content": user})
        try:
            reply, messages = handle_turn(messages)
        except Exception as e:
            print(f"[loop error] {e}\n")
            continue
        print(f"\nagent> {reply}\n")


if __name__ == "__main__":
    main()
