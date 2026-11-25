"""
dispatcher.py - the front door. Type a plain-language request, it figures out
which existing tool handles it and runs that, instead of you remembering
which script and flags to use.

Now constitutional: every routed action passes through the AxiomOS gate before
it runs. The gate logs it to the ledger and hard-denies clear violations.
Open-ended capabilities (general_agent, write_code) also get full LLM judgment;
structured ones rely on their own built-in safety plus the gate's logging/hard rules.

This does NOT replace the safety behavior already built into each tool:
- recon_tool.py still refuses anything not confirmed in-scope
- agent_tools.py's run_shell still asks you to confirm
- report_drafter.py still only drafts, never submits

All model calls go through core.models (no `ollama` library dependency).

Run (from the project root ~/axiom):
    python3 -m dispatcher "find new bug bounty programs"
    python3 -m dispatcher "research SQL injection for me"
    python3 -m dispatcher "write a script that renames all files in a folder to lowercase"
    python3 -m dispatcher "spec out a rate-limited retry wrapper with backoff"
    python3 -m dispatcher "draft a report for finding 2 for hackerone"
    python3 -m dispatcher "check if app.example.com is in scope for program 1 and scan its subdomains"

Or run with no argument for an interactive prompt loop:
    python3 -m dispatcher
"""
import argparse
import json
import re
import subprocess
import sys

from core import models
from core import config
from core.axiom_gate import evaluate_action

MODEL = config.ROUTER_MODEL

# Capabilities the model can route to. Keep descriptions specific - this is
# what the model uses to decide, so vague descriptions cause bad routing.
CAPABILITIES = """
1. research          - Look up and build structured notes on a topic.
                        Runs research_agent.py "<topic>"
2. summarize_research - Summarize everything already researched on a topic.
                        Runs research_agent.py "<topic>" --summary
3. write_code        - Write and test a piece of code for a described task.
                        Runs code_agent.py "<task>"
4. general_agent     - A flexible task needing file ops, web search, or shell
                        commands that doesn't fit the other categories.
                        Runs agent_tools.py "<task>"
5. check_programs    - Check bounty platforms for new programs.
                        Runs program_watcher.py
6. recon             - Run recon (subdomains or ports) against a specific
                        asset for a specific program id. REQUIRES program_id,
                        asset, and recon_type (subdomains or ports).
                        Runs recon_tool.py --program <id> --asset <asset> --type <type>
7. draft_report      - Draft a bounty report for an already-logged finding.
                        REQUIRES finding_id and platform (hackerone/bugcrowd/generic).
                        Runs report_drafter.py --finding <id> --platform <platform>
8. list_findings     - List findings already logged in the database.
                        Runs report_drafter.py --list
9. sync_scope        - Pull a program's official scope into the local database so
                        recon is gated to exactly what the program authorizes.
                        REQUIRES program_id. Runs program_watcher.py --sync-scope <id>
10. check_duplicate  - Check whether a logged finding is likely already publicly
                        disclosed, before drafting/submitting. REQUIRES finding_id.
                        Runs duplicate_checker.py --finding <id>
11. spec             - Generate a structured build spec (interface, acceptance
                        tests, edge cases, open questions) from a task WITHOUT
                        building it. Use when the user asks to "spec out", "write
                        a spec for", or "plan" something before any code.
                        Runs spec_agent.py "<task>"
12. unclear          - The request doesn't map cleanly to any tool, or is
                        missing required info (like which program_id or
                        finding_id). Use this rather than guessing IDs.
"""

ROUTING_PROMPT = """
You are a router. Given a user's request, decide which ONE capability below
fits best and extract the arguments it needs.

{capabilities}

Reply with ONLY a JSON object in this exact shape, nothing else:
{{"capability": "<name>", "args": {{...}}, "reasoning": "<one short sentence>"}}

Argument keys to use depending on capability:
- research / summarize_research: {{"topic": "..."}}
- write_code: {{"task": "..."}}
- general_agent: {{"task": "..."}}
- check_programs: {{}}
- recon: {{"program_id": <int>, "asset": "...", "recon_type": "subdomains" or "ports"}}
- draft_report: {{"finding_id": <int>, "platform": "hackerone" or "bugcrowd" or "generic"}}
- list_findings: {{}}
- sync_scope: {{"program_id": <int>}}
- check_duplicate: {{"finding_id": <int>}}
- spec: {{"task": "..."}}
- unclear: {{"reason": "..."}}

If the request requires a program_id or finding_id the user didn't give you,
use "unclear" rather than inventing a number.

User request: "{request}"
"""

CLARIFY_PROMPT = """
You tried to route this request but it was unclear:

Original request: "{request}"
Why it was unclear: "{reason}"

Ask ONE short, specific question that would get the missing information you
need to route this correctly. Just the question, nothing else - no preamble.
"""

# Capabilities that only read data / don't change anything or spend real
# resources - these run without an extra confirmation prompt. spec generation
# is inert (produces text, touches nothing), so it belongs here.
READ_ONLY = {"summarize_research", "check_programs", "list_findings", "spec"}

# Open-ended capabilities get full constitutional (LLM) judgment at the gate.
# The rest have their own built-in safety (recon scope check, report drafter
# drafts-only, etc.), so the gate logs them and applies hard-deny rules but
# skips the LLM judgment that would false-block legitimate security work.
OPEN_ENDED = {"general_agent", "write_code"}


def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def route(request):
    prompt = ROUTING_PROMPT.format(capabilities=CAPABILITIES, request=request)
    try:
        content = models.chat([{"role": "user", "content": prompt}], MODEL)
    except models.ModelError as e:
        print(f"[router] model error: {e}")
        return None
    parsed = extract_json(content)
    if not parsed:
        print("[router] model did not return valid routing JSON:")
        print(content)
        return None
    return parsed


def build_command(capability, args):
    if capability == "research":
        return [sys.executable, "-m", "bounty.research_agent", args["topic"]]
    if capability == "summarize_research":
        return [sys.executable, "-m", "bounty.research_agent", args["topic"], "--summary"]
    if capability == "write_code":
        return [sys.executable, "-m", "capabilities.code_agent", args["task"]]
    if capability == "general_agent":
        return [sys.executable, "-m", "capabilities.agent_tools", args["task"]]
    if capability == "check_programs":
        return [sys.executable, "-m", "bounty.program_watcher"]
    if capability == "recon":
        return [
            sys.executable, "-m", "bounty.recon_tool",
            "--program", str(args["program_id"]),
            "--asset", args["asset"],
            "--type", args["recon_type"],
        ]
    if capability == "draft_report":
        return [
            sys.executable, "-m", "bounty.report_drafter",
            "--finding", str(args["finding_id"]),
            "--platform", args["platform"],
        ]
    if capability == "list_findings":
        return [sys.executable, "-m", "bounty.report_drafter", "--list"]
    if capability == "sync_scope":
        return [sys.executable, "-m", "bounty.program_watcher", "--sync-scope", str(args["program_id"])]
    if capability == "check_duplicate":
        return [sys.executable, "-m", "bounty.duplicate_checker", "--finding", str(args["finding_id"])]
    if capability == "spec":
        return [sys.executable, "-m", "capabilities.spec_agent", args["task"]]
    return None

def ask_clarifying_question(request, reason):
    prompt = CLARIFY_PROMPT.format(request=request, reason=reason)
    try:
        return models.chat([{"role": "user", "content": prompt}], MODEL).strip()
    except models.ModelError:
        return "Could you add the missing detail (program id, finding id, or exact topic)?"


def handle(request, clarify_rounds=0, max_clarify_rounds=2):
    decision = route(request)
    if not decision:
        return

    capability = decision.get("capability")
    args = decision.get("args", {})
    reasoning = decision.get("reasoning", "")

    if capability == "unclear" or not capability:
        reason = args.get("reason", reasoning) or "missing required detail"

        if clarify_rounds >= max_clarify_rounds:
            print(f"[dispatcher] Still unclear after {max_clarify_rounds} tries: {reason}")
            print("Try starting over with specifics (program id, finding id, exact topic/task).")
            return

        question = ask_clarifying_question(request, reason)
        print(f"[dispatcher] Need more info: {question}")
        answer = input("> ").strip()
        if not answer or answer.lower() in ("quit", "exit", "nevermind", "never mind"):
            print("[dispatcher] Cancelled.")
            return

        # Fold the answer into the original request and try routing again
        combined_request = f"{request}\n\nAdditional detail: {answer}"
        handle(combined_request, clarify_rounds=clarify_rounds + 1, max_clarify_rounds=max_clarify_rounds)
        return

    try:
        cmd = build_command(capability, args)
    except KeyError as e:
        print(f"[dispatcher] Router picked '{capability}' but was missing argument {e}.")
        print("Try rephrasing with that detail included.")
        return

    print(f"[dispatcher] Routing to: {capability}")
    print(f"[dispatcher] Reasoning: {reasoning}")
    print(f"[dispatcher] Command: {' '.join(cmd)}")

    # --- AxiomOS constitutional gate: log every action, hard-deny violations ---
    verdict = evaluate_action(
        {"tool": capability, "args": args},
        requester="dispatcher",
        use_llm=capability in OPEN_ENDED,
    )
    print(f"[gate] {verdict['decision']}: {verdict.get('reasoning', '')}")
    if verdict["decision"] == "blocked":
        print(f"[gate] Refused ({verdict.get('axiom_triggered')}). Nothing was run.")
        return

    # Gate pending_confirmation forces a human check; otherwise read-only runs free.
    needs_confirm = verdict["decision"] == "pending_confirmation" or capability not in READ_ONLY
    if needs_confirm:
        confirm = input("Run this? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

    subprocess.run(cmd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("request", nargs="?", help="plain-language request")
    args = parser.parse_args()

    if args.request:
        handle(args.request)
    else:
        print("Dispatcher ready. Type a request, or 'quit' to exit.")
        while True:
            try:
                text = input("\n> ").strip()
            except EOFError:
                break
            if text.lower() in ("quit", "exit"):
                break
            if text:
                handle(text)
