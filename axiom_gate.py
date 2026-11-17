"""
axiom_gate.py — the constitutional gate.

Every action an agent attempts is evaluated here before it runs. Two layers:

  1. A deterministic rule layer, in plain code, that hard-blocks known-dangerous
     operations (destructive shell, writes outside the project, touching the
     gate/ledger themselves) and fast-allows obviously safe reads.
  2. A model layer that judges the ambiguous cases against the constitution.

It FAILS CLOSED: if the model can't be reached or returns something unusable,
the action is denied, not allowed. Every decision is written to the ledger.
"""
import os
import re
import json
import requests

from axiom_ledger import write_entry

OLLAMA_CHAT     = "http://localhost:11434/api/chat"
GATE_MODEL      = "qwen3:4b"        # any small local model works
REQUEST_TIMEOUT = 60

# Write-like actions must stay under this root. Defaults to the working dir.
PROJECT_ROOT = os.path.abspath(os.getcwd())

# When False, the gate uses ONLY the deterministic rules and never calls the
# model (useful when a large model needs all available memory).
USE_LLM_GATE = True

# --- deterministic hard-deny patterns (checked before the model) ---
_DANGEROUS = [
    r"\brm\s+-[a-z]*r[a-z]*f",            # rm -rf and variants
    r"\brm\s+-[a-z]*f[a-z]*r",
    r"\bmkfs\b",
    r"\bdd\s+.*\bof=/dev/",
    r":\(\)\s*{\s*:\s*\|\s*:&\s*}\s*;",   # fork bomb
    r"\b(curl|wget)\b.*\|\s*(sh|bash)",   # pipe-to-shell
    r"\bchmod\s+-R\s+777\s+/",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|halt|poweroff)\b",
    r"\b(userdel|usermod|passwd)\b",
    r"\biptables\s+-F",
]
_DANGEROUS = [re.compile(p, re.IGNORECASE) for p in _DANGEROUS]

_PROTECTED   = ("axiom_gate.py", "axiom_ledger.py", "constitution")  # Article 7.6
_WRITE_TOOLS = ("write", "save", "delete", "remove", "move", "append", "edit")
_SAFE_READONLY = ("read_file", "list_dir", "recall", "graph_query")   # auto-allowed reads

CONSTITUTIONAL_PROMPT = """
You are the constitutional gate of AxiomOS. Your sole function is to evaluate whether a requested action violates the Axiom Constitution.

IMMUTABLE PRINCIPLES (Article 2):
2.1 Human Autonomy — no action may coerce or override human decision-making
2.2 Safety Before Action — default to inaction when safety is uncertain. No irreversible action without explicit confirmation.
2.3 Local-First Privacy — no data transmitted without explicit consent
2.4 Anti-Othering — birth traits never influence access or decisions
2.5 Cognitive Respect — the system adapts to the person, never penalizes cognitive difference
2.6 Clarity Over Cleverness — all actions must be explainable in plain language
2.7 Architecture Over Personality — no individual is irreplaceable

PROHIBITED ACTIONS (Article 7):
7.1 No synthetic media of real people without consent
7.2 No psychological manipulation or dark patterns
7.3 No identity exploitation
7.4 No centralized control accumulation
7.5 No surveillance without consent
7.6 No constitutional self-modification without process

Respond in JSON only. No other text:
{"decision": "allowed"|"blocked"|"pending_confirmation", "axiom_triggered": "article or null", "reasoning": "plain language"}
"""


def _normalize(action):
    """Accept both a dict {tool, args} and a legacy string."""
    if isinstance(action, dict):
        return str(action.get("tool", "")), (action.get("args") or {}), json.dumps(action)
    return "", {}, str(action)


def _strings(args):
    out = []
    if isinstance(args, dict):
        for v in args.values():
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, (list, tuple)):
                out += [x for x in v if isinstance(x, str)]
            elif isinstance(v, dict):
                out += _strings(v)
    return out


def _block(axiom, reason):
    return {"decision": "blocked", "axiom_triggered": axiom,
            "reasoning": reason, "layer": "deterministic"}


def _deterministic(tool, args, text):
    """Hard rules in code. Returns a decision, or None to defer to the model."""
    blob = text + " " + " ".join(_strings(args))

    # Hard denies apply to every tool.
    for pat in _DANGEROUS:
        if pat.search(blob):
            return _block("7.4 Destructive/centralized control",
                          f"hard-deny pattern: {pat.pattern}")

    # Read-only tools are low risk: auto-allow once they clear the deny patterns.
    if tool in _SAFE_READONLY:
        return {"decision": "allowed", "axiom_triggered": None,
                "reasoning": f"{tool} is read-only, auto-allowed",
                "layer": "deterministic-allow"}

    # Protect system files and the project boundary for writes/exec.
    low = blob.lower()
    for p in _PROTECTED:
        if p in low:
            return _block("7.6 No constitutional self-modification",
                          "action references a protected system file")

    if any(k in tool.lower() for k in _WRITE_TOOLS):
        for v in _strings(args):
            if v.startswith("/") and not v.startswith(PROJECT_ROOT):
                return _block("2.3 Local-First / path escape",
                              f"write outside project root: {v}")
    return None


def _llm_gate(text, requester):
    payload = {
        "model": GATE_MODEL,
        "messages": [
            {"role": "system", "content": CONSTITUTIONAL_PROMPT},
            {"role": "user",   "content": f"Evaluate this action: {text}\nRequested by: {requester}"},
        ],
        "stream": False,
        "think": False,          # reasoning models: keep the verdict in `content`
        "format": "json",
    }
    try:
        r = requests.post(OLLAMA_CHAT, json=payload, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        result = json.loads(r.json()["message"]["content"])
    except Exception as e:                       # fail closed: any error is a block
        return {"decision": "blocked", "axiom_triggered": None,
                "reasoning": f"gate error, failing closed: {e}", "layer": "llm-error"}

    result.setdefault("decision", "blocked")
    result.setdefault("axiom_triggered", None)
    result.setdefault("reasoning", "")
    if result["decision"] not in ("allowed", "blocked", "pending_confirmation"):
        result = {"decision": "blocked", "axiom_triggered": None,
                  "reasoning": "unrecognized decision, failing closed"}
    result["layer"] = "llm"
    return result


def evaluate_action(action, requester, use_llm=None):
    """Judge an action and log the decision. use_llm forces the model layer
    on/off for this call; None falls back to the global USE_LLM_GATE."""
    tool, args, text = _normalize(action)
    result = _deterministic(tool, args, text)
    if result is None:
        do_llm = USE_LLM_GATE if use_llm is None else use_llm
        if do_llm:
            result = _llm_gate(text, requester)
        else:
            result = {"decision": "allowed", "axiom_triggered": None,
                      "reasoning": "passed deterministic rules (no model judgment for this action)",
                      "layer": "deterministic-pass"}

    write_entry(
        action=text,
        requester=requester,
        decision=result["decision"],
        axiom_triggered=result.get("axiom_triggered"),
        reasoning=result.get("reasoning"),
    )
    return result


if __name__ == "__main__":
    # These run with the model layer off, so they show the DETERMINISTIC rules
    # only (no Ollama needed). With USE_LLM_GATE=True the model layer additionally
    # judges semantic cases — e.g. "transmit the user's location to an external
    # server" would be blocked under Article 7.5, which no regex can catch.
    tests = [
        {"tool": "run_shell",  "args": {"cmd": "rm -rf /"}},          # hard-deny pattern
        {"tool": "read_file",  "args": {"path": "notes.txt"}},        # safe read, auto-allow
        {"tool": "write_file", "args": {"path": "/etc/hosts", "data": "x"}},  # path escape
    ]
    for a in tests:
        r = evaluate_action(a, "demo", use_llm=False)
        print(f"{r['decision']:20} {r.get('axiom_triggered')}  <- {a}")
