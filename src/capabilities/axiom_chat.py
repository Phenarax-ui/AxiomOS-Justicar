"""
axiom_chat.py — the conversational AxiomOS agent (native Ollama tool calling).

You talk to it; it reasons, calls tools, and loops. gpt-oss returns structured
tool_calls; the loop routes each through the AxiomOS gate, runs it, and feeds the
result back. The gate logs every attempt to the ledger. Code-executing tools
(run_python, write_and_test) run in a firejail sandbox. The gate judges the
REQUEST; the sandbox contains the EXECUTION.

(Formerly flint_loop.py — renamed; nothing else imported it.)

Tools: read_file, write_file, list_dir, run_python, web_search, run_shell,
       write_spec, write_and_test, plus memory + bounty tools.

All model calls go through core.models (no `ollama` library dependency).

Setup:
    sudo apt install firejail
    ollama pull gpt-oss:20b && ollama pull qwen3:4b
Run (from the project root ~/axiom):
    python3 -m capabilities.axiom_chat
"""

import os
import re
import sys
import json
import keyword
import shutil
import tempfile
import subprocess

try:
    from ddgs import DDGS                 # current package name
except ImportError:
    try:
        from duckduckgo_search import DDGS   # older package name
    except ImportError:
        DDGS = None                          # web_search disabled until installed

from core import memory
from core import models
from core import config
from core.axiom_gate import evaluate_action
from bounty import findings, program_watcher, duplicate_checker
from capabilities.spec_agent import generate_spec
from capabilities.code_agent import constitutional_code_review   # reused to vet made tools

MODEL       = config.CHAT_MODEL
NUM_CTX     = 16384
REQUESTER   = "agent"
GEN_TIMEOUT = 600

# sandboxed-execution settings (run_python + write_and_test + made tools)
CODER_MODEL      = MODEL
CODE_MAX_TRIES   = 4
CODE_TIMEOUT     = 15
SANDBOX_REQUIRED = True

# firejail --private swaps in a THROWAWAY $HOME (that's the "no real files"
# guarantee), which hides a venv interpreter living under ~. Run sandboxed code
# with a SYSTEM python (outside $HOME) so --private can't hide it. Sandboxed code
# is stdlib-only pure compute, so it never needs the venv's packages anyway.
_SANDBOX_PY = next((p for p in ("/usr/bin/python3", "/usr/local/bin/python3", "/bin/python3")
                    if os.path.exists(p)), sys.executable)

SYSTEM_PROMPT = """You are a coding assistant running locally inside AxiomOS.
You have these tools: read_file, write_file, list_dir, run_python, web_search,
run_shell, write_spec (plan a coding task as a structured spec before building),
write_and_test (writes Python, runs it sandboxed, auto-fixes), make_tool (define a
NEW sandboxed computation tool when you need a reusable transform you don't already
have — it computes only, with NO network and NO file access), and a memory:
recall (search what you already know), remember (store a durable fact, with edges
linking entities), and graph_query (traverse the knowledge graph).
You also have bounty tools: check_programs (find new bounty programs — use this,
do NOT web_search or curl the directories by hand), log_finding (record a
vulnerability), and list_findings.
For a NON-TRIVIAL coding task, call write_spec FIRST to lay out the interface,
acceptance tests, and edge cases; show the user the spec, then build to it with
write_and_test. Skip the spec for trivial one-liners.
Use make_tool ONLY for pure, reusable computation you have no tool for (a parser,
a transform, an algorithm). It is sandboxed: no network, no file access. For
anything that needs the network or real files, use the existing gated tools,
never a made tool.
When the user asks what you know about something — or any question memory might
answer — call recall FIRST (and graph_query for a specific entity like a host or
program), BEFORE any web_search or shell command. Only use web_search or run_shell
if memory lacks the answer or the user explicitly asks for fresh or live data.
Remember durable findings so they persist across sessions. When asked to remember,
note, or record a fact, ALWAYS use the remember tool — never write_file, which is
only for creating real files like code or reports. Use the other tools when the task
calls for them rather than answering from memory. Every tool call is checked
by a constitutional gate before it runs; if one is blocked you will be told why —
adapt and find a safe path. Explain results plainly."""

CODER_SYSTEM = (
    "You are a careful Python programmer. Given a task, respond with a single "
    "Python code block only — no prose before or after. The code must run "
    "standalone with python3 and print output showing it works, including test "
    "cases. Use only the standard library unless the task names another package."
)


# --------------------------------------------------------------------------
# Sandbox helper (shared by run_python and write_and_test)
# --------------------------------------------------------------------------
def _run_in_sandbox(code):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        fj = shutil.which("firejail")
        if fj:
            cmd = [fj, "--quiet", "--net=none", "--private", _SANDBOX_PY, path]
        elif SANDBOX_REQUIRED:
            return False, ("SANDBOX UNAVAILABLE: firejail not installed, refusing to run "
                           "generated code. Install it: sudo apt install firejail")
        else:
            cmd = [_SANDBOX_PY, path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CODE_TIMEOUT)
        ok = r.returncode == 0
        return ok, (r.stdout if ok else r.stdout + r.stderr) or "(no output)"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {CODE_TIMEOUT}s (possible infinite loop)"
    finally:
        os.unlink(path)


# --------------------------------------------------------------------------
# Tools (names and args match agent_tools.py; write_spec is new)
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
    ok, out = _run_in_sandbox(code)           # sandboxed, no network, throwaway home
    return out


def tool_web_search(query):
    if DDGS is None:
        return ("web_search unavailable: the 'ddgs' package isn't installed. "
                "Install it in your project venv (pip install ddgs) to enable web search.")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return "\n".join(f"- {r['title']}: {r['href']}" for r in results) or "No results."
    except Exception as e:
        return f"ERROR: {e}"


def tool_run_shell(command):                  # no built-in prompt; the gate decides
    try:
        out = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return (out.stdout + out.stderr)[:4000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timed out after 30 seconds"


def tool_remember(content, edges=None):
    return memory.remember(content, edges=edges, source="agent")


def tool_recall(query):
    return memory.recall(query)


def tool_graph_query(node, relation=None, depth=1):
    return memory.graph_query(node, relation=relation, depth=depth)


def tool_log_finding(program_id, title, severity=None, evidence=None):
    return findings.log_finding(program_id, title, severity=severity, evidence=evidence)


def tool_list_findings(program_id=None):
    return findings.list_findings(program_id=program_id)


def tool_check_programs():
    out = []
    for platform, fetch in (("HackerOne", program_watcher.fetch_hackerone_programs),
                            ("Bugcrowd", program_watcher.fetch_bugcrowd_programs)):
        try:
            new = program_watcher.sync_new_programs(platform, fetch())
            out += [f"- {p['name']} ({p['url']})" for p in new]
        except Exception as e:
            out.append(f"[{platform}] error: {e}")
    if not out:
        return ("No new programs found. Note: the public directories are JS-rendered, so a "
                "plain scrape often sees nothing — the HackerOne API would be more reliable.")
    return "New programs added:\n" + "\n".join(out)


def tool_sync_scope(program_id):
    return program_watcher.sync_scope(program_id)


def tool_check_duplicate(finding_id):
    return duplicate_checker.check_duplicate(finding_id)


def _extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def tool_write_spec(task):
    # Uses the loop's OWN loaded model (CODER_MODEL = MODEL), not spec_agent's
    # default, so speccing mid-conversation doesn't force an Ollama model reload.
    try:
        spec = generate_spec(task, model=CODER_MODEL)
        return json.dumps(spec, indent=2)
    except Exception as e:
        return f"ERROR: {e}"


def tool_write_and_test(task):
    msgs = [{"role": "system", "content": CODER_SYSTEM},
            {"role": "user",   "content": task}]
    code, out = "", ""
    for attempt in range(1, CODE_MAX_TRIES + 1):
        reply = models.chat(msgs, CODER_MODEL, think=False)     # was ollama.chat(...)
        code = _extract_code(reply)
        ok, out = _run_in_sandbox(code)
        if ok:
            return json.dumps({"status": "passed", "attempts": attempt,
                               "code": code, "output": out})
        msgs.append({"role": "assistant", "content": reply})
        msgs.append({"role": "user",
                     "content": f"That failed when run:\n\n{out}\n\n"
                                "Fix it and respond with a single corrected code block only."})
    return json.dumps({"status": "failed", "attempts": CODE_MAX_TRIES,
                       "code": code, "output": out})


# --------------------------------------------------------------------------
# Runtime tool creation — the agent can extend its COMPUTE, never its ACCESS.
# A made tool is a named Python snippet that runs network-isolated in the
# sandbox (no net, throwaway home => no real files). It is reviewed against the
# constitution before it can exist, every call still passes the gate, and it is
# session-only (gone on restart). It can process data; it cannot reach out.
# --------------------------------------------------------------------------
_DYNAMIC_TOOLS = {}   # name -> code string (in-memory, this session only)


def _run_dynamic_tool(name, args):
    """Execute a made tool in the sandbox: inject its args, call run(), print JSON."""
    code = _DYNAMIC_TOOLS.get(name)
    if code is None:
        return f"error: made tool '{name}' is not defined"
    args_json = json.dumps(args)
    harness = (
        code
        + "\n\nif __name__ == '__main__':\n"
        + "    import json as _j\n"
        + f"    _a = _j.loads({args_json!r})\n"
        + "    print(_j.dumps(run(**_a)))\n"
    )
    ok, out = _run_in_sandbox(harness)     # firejail --net=none --private
    return out


def tool_make_tool(name, description, code, parameters=None, **_ignored):
    """Define a new sandboxed computation tool the agent can then call.

    Guardrails (why this doesn't blow a hole in the constitution):
      * name must be a fresh identifier — can't shadow a built-in tool
      * code must compile and define run(**kwargs)
      * code is constitutionally reviewed BEFORE registration (network/exec/secret
        access is denied here, on this loop's model to avoid a reload)
      * at call time it runs network-isolated with a throwaway home (no real files)
      * the call still passes the gate like any other tool, and it is session-only
    """
    if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
        return f"rejected: '{name}' is not a valid tool name"
    if name in TOOLS:
        return f"rejected: a tool named '{name}' already exists — cannot override a built-in tool"
    if not isinstance(code, str) or "def run(" not in code:
        return "rejected: code must define a function `run(**kwargs)`"
    try:
        compile(code, f"<made_tool:{name}>", "exec")
    except SyntaxError as e:
        return f"rejected: code has a syntax error: {e}"

    allowed, reason = constitutional_code_review(code, model=MODEL)
    if not allowed:
        return f"rejected by the constitution: {reason}"

    _DYNAMIC_TOOLS[name] = code
    TOOLS[name] = lambda **kw: _run_dynamic_tool(name, kw)
    TOOL_SPECS.append({
        "type": "function",
        "function": {
            "name": name,
            "description": f"{description} (made tool: sandboxed, no network/files)",
            "parameters": {"type": "object",
                           "properties": parameters or {},
                           "required": list((parameters or {}).keys())},
        },
    })
    return (f"tool '{name}' created and ready — it runs sandboxed (no network, no file "
            f"access) and every call still passes the gate. You can call it now.")


TOOLS = {
    "read_file":      tool_read_file,
    "write_file":     tool_write_file,
    "list_dir":       tool_list_dir,
    "run_python":     tool_run_python,
    "web_search":     tool_web_search,
    "run_shell":      tool_run_shell,
    "write_spec":     tool_write_spec,
    "write_and_test": tool_write_and_test,
    "make_tool":      tool_make_tool,
    "remember":       tool_remember,
    "recall":         tool_recall,
    "graph_query":    tool_graph_query,
    "log_finding":    tool_log_finding,
    "list_findings":  tool_list_findings,
    "check_programs": tool_check_programs,
    "sync_scope":     tool_sync_scope,
    "check_duplicate": tool_check_duplicate,
}

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a UTF-8 text file (first 8000 chars).",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": ("Write text to a real file on disk (code, a config, a report). "
                        "NOT for storing facts or notes to remember — use `remember` for that."),
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                      "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "List the entries in a directory.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "run_python",
        "description": "Run a Python snippet in a network-isolated sandbox; returns its output.",
        "parameters": {"type": "object",
                       "properties": {"code": {"type": "string"}},
                       "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web (DuckDuckGo); returns the top result titles and links.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "run_shell",
        "description": "Run a shell command, returning combined stdout and stderr.",
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "write_spec",
        "description": ("Produce a structured build spec (interface signatures, acceptance "
                        "tests, edge cases, open questions) for a coding task WITHOUT building "
                        "it. Call this before write_and_test on any non-trivial task, show the "
                        "user the spec, then build to it. Skip for trivial one-liners. Returns "
                        "the spec as JSON."),
        "parameters": {"type": "object",
                       "properties": {"task": {"type": "string"}},
                       "required": ["task"]}}},
    {"type": "function", "function": {
        "name": "write_and_test",
        "description": ("Write Python code for a task, run it in a sandbox, and auto-fix on "
                        "failure. Returns JSON with status, final code, and output."),
        "parameters": {"type": "object",
                       "properties": {"task": {"type": "string"}},
                       "required": ["task"]}}},
    {"type": "function", "function": {
        "name": "make_tool",
        "description": ("Define a NEW reusable tool you can then call. Use ONLY when a task needs "
                        "a reusable computation you have no tool for (a parser, a transform, an "
                        "algorithm). The made tool runs SANDBOXED: no network, no file access — it "
                        "computes and returns a value, nothing more. For anything needing the "
                        "network or real files, use the existing gated tools instead. Provide code "
                        "defining `def run(**kwargs)` that returns a JSON-serializable value."),
        "parameters": {"type": "object",
                       "properties": {
                           "name": {"type": "string",
                                    "description": "new tool name: a valid identifier, not an existing tool"},
                           "description": {"type": "string", "description": "what the tool does"},
                           "parameters": {"type": "object",
                                          "description": "JSON-schema properties for the tool's args, "
                                                         "e.g. {\"text\": {\"type\": \"string\"}}"},
                           "code": {"type": "string",
                                    "description": "Python defining def run(**kwargs) -> JSON-serializable result"}},
                       "required": ["name", "description", "code"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": ("Store a durable fact or finding in the agent's persistent memory and "
                        "knowledge graph, with optional edges linking entities. ALWAYS use this "
                        "(never write_file) when asked to remember, note, record, or save a fact, "
                        "or when you learn something durable worth keeping across sessions. "
                        "Allowed relations: found_on, in_scope_of, affects, uses_tech, "
                        "has_endpoint, similar_to, duplicate_of, reported_to, related_to, note."),
        "parameters": {"type": "object",
                       "properties": {
                           "content": {"type": "string", "description": "the fact to remember"},
                           "edges": {"type": "array",
                                     "description": "optional list of {src, relation, dst} links",
                                     "items": {"type": "object",
                                               "properties": {"src": {"type": "string"},
                                                              "relation": {"type": "string"},
                                                              "dst": {"type": "string"}}}}},
                       "required": ["content"]}}},
    {"type": "function", "function": {
        "name": "recall",
        "description": "Search memory (stored facts and past research notes) for a query.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "graph_query",
        "description": "Traverse the knowledge graph from a node; returns edges out to `depth` hops.",
        "parameters": {"type": "object",
                       "properties": {
                           "node": {"type": "string"},
                           "relation": {"type": "string", "description": "optional relation filter"},
                           "depth": {"type": "integer", "description": "hops to traverse (default 1)"}},
                       "required": ["node"]}}},
    {"type": "function", "function": {
        "name": "log_finding",
        "description": ("Record a suspected or verified vulnerability in the findings database. "
                        "Keep evidence minimal — a description of the proof, never real user data."),
        "parameters": {"type": "object",
                       "properties": {
                           "program_id": {"type": "integer"},
                           "title": {"type": "string"},
                           "severity": {"type": "string", "description": "low, medium, high, or critical"},
                           "evidence": {"type": "string", "description": "short description of the proof"}},
                       "required": ["program_id", "title"]}}},
    {"type": "function", "function": {
        "name": "list_findings",
        "description": "List logged findings, optionally filtered to one program.",
        "parameters": {"type": "object",
                       "properties": {"program_id": {"type": "integer",
                                                     "description": "optional program filter"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "check_programs",
        "description": ("Check public bounty directories (HackerOne, Bugcrowd) for new programs "
                        "and add new ones to the database. USE THIS to find bounty programs — "
                        "do not web_search or curl the directories by hand. Reads public pages "
                        "only; never touches a target."),
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "sync_scope",
        "description": ("Pull a bounty program's official scope from HackerOne into the local "
                        "scope database, so recon against it is gated to exactly what the program "
                        "authorizes. Do this before recon on a program's assets. Needs the program id."),
        "parameters": {"type": "object",
                       "properties": {"program_id": {"type": "integer"}},
                       "required": ["program_id"]}}},
    {"type": "function", "function": {
        "name": "check_duplicate",
        "description": ("Before drafting or submitting, check whether a logged finding is likely "
                        "already publicly disclosed (searches public sources and assesses overlap). "
                        "Heuristic, not a guarantee. Needs the finding id."),
        "parameters": {"type": "object",
                       "properties": {"finding_id": {"type": "integer"}},
                       "required": ["finding_id"]}}},
]


# --------------------------------------------------------------------------
# Ollama (native tool calling, via core.models) + gated execution
# --------------------------------------------------------------------------
def _chat(messages):
    # was a hand-rolled requests.post; now one shared call that returns the
    # full message (content + any tool_calls).
    return models.chat_tools(messages, MODEL, TOOL_SPECS,
                             num_ctx=NUM_CTX, timeout=GEN_TIMEOUT)


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
                result = (f"BLOCKED by AxiomOS gate "
                          f"({verdict.get('axiom_triggered')}): {verdict.get('reasoning')}")

            print(f"  · {name}({args}) -> {decision}")
            messages.append({"role": "tool", "tool_name": name, "content": result})


def read_user_input():
    """Read a possibly multi-line message.

    Paste or type as many lines as you like — blank lines included — then put
    /send on its own line to submit, or /quit to exit. Replaces the old
    single-line input(), which broke on any pasted prompt containing a blank
    line: each blank line submitted an empty message and chopped the paste.
    """
    print("you> (paste your message, then /send to submit — /quit to exit)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:            # Ctrl-D
            if lines:
                break               # submit what's been typed so far
            return None             # quit on an empty buffer
        except KeyboardInterrupt:   # Ctrl-C
            return None             # quit
        stripped = line.strip()
        if stripped == "/send":
            break
        if stripped == "/quit":
            return None
        lines.append(line)
    return "\n".join(lines).strip()


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("AxiomOS chat — every tool call passes the gate.")
    print("Paste a message, then /send to submit. /quit (or Ctrl-C) to exit.\n")
    while True:
        user = read_user_input()
        if user is None:            # /quit, Ctrl-C, or Ctrl-D on empty
            print("\nbye")
            break
        if not user:                # empty submission — prompt again
            continue
        messages.append({"role": "user", "content": user})
        try:
            reply, messages = handle_turn(messages)
        except Exception as e:
            print(f"[loop error] {e}\n")
            continue
        print(f"\nmodel> {reply}\n")


if __name__ == "__main__":
    main()
