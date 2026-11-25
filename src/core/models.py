"""
models.py - the one place AxiomOS talks to Ollama.

Every component that needs a model (the gate, the tutor, explain, flint,
code_agent) calls through here instead of writing its own requests.post. One
host, one timeout policy, one place to handle errors. Point OLLAMA_HOST at a
remote IRWIN over Tailscale someday and every caller follows - change it once.

Four entry points, matching how your code already uses Ollama:
    chat(messages, model)        -> text        (code_agent / flint style)
    chat_json(messages, model)   -> dict        (the gate - parsed JSON)
    generate(prompt, model)      -> text        (the tutor - one prompt)
    stream(prompt, model)        -> yields text (explain.py - live output)
"""
import json
import requests
from core import config

OLLAMA_HOST = config.OLLAMA_HOST
DEFAULT_TIMEOUT = 120


class ModelError(RuntimeError):
    """Any model call that fails: network, HTTP, or a malformed response.
    Callers that must fail safe (the gate) catch this and block."""


def chat(messages, model, *, fmt=None, think=False, options=None, timeout=DEFAULT_TIMEOUT):
    """One /api/chat round. Returns the assistant's text content.
    fmt='json' asks Ollama to constrain the reply to JSON (you still parse it).
    options passes Ollama generation settings, e.g. {"temperature": 0}."""
    payload = {"model": model, "messages": messages, "stream": False, "think": think}
    if fmt:
        payload["format"] = fmt
    if options:
        payload["options"] = options
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (requests.RequestException, KeyError, ValueError) as e:
        raise ModelError(f"chat() failed for {model}: {e}") from e


def chat_tools(messages, model, tools, *, num_ctx=None, timeout=DEFAULT_TIMEOUT):
    """A /api/chat round that may come back with tool_calls. Returns the FULL
    message dict (content, tool_calls, thinking, ...), because a tool-calling
    loop needs the whole thing, not just the text. Used by agent loops like
    flint. num_ctx sets the context window when the loop needs a big one."""
    payload = {"model": model, "messages": messages, "tools": tools, "stream": False}
    if num_ctx is not None:
        payload["options"] = {"num_ctx": num_ctx}
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()["message"]
    except (requests.RequestException, KeyError, ValueError) as e:
        raise ModelError(f"chat_tools() failed for {model}: {e}") from e


def chat_json(messages, model, **kw):
    """chat() that also parses the reply as JSON. Raises ModelError if the
    model returned something that isn't valid JSON."""
    kw.setdefault("fmt", "json")
    text = chat(messages, model, **kw)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"{model} returned non-JSON: {text[:200]!r}") from e


def generate(prompt, model, *, timeout=DEFAULT_TIMEOUT):
    """One /api/generate call, non-streaming. Returns the full text."""
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/generate",
                          json={"model": model, "prompt": prompt, "stream": False},
                          timeout=timeout)
        r.raise_for_status()
        return r.json()["response"].strip()
    except (requests.RequestException, KeyError, ValueError) as e:
        raise ModelError(f"generate() failed for {model}: {e}") from e


def stream(prompt, model, *, timeout=DEFAULT_TIMEOUT):
    """Stream a /api/generate call, yielding text chunks as they arrive so the
    caller can print them live. Raises ModelError on failure."""
    try:
        with requests.post(f"{OLLAMA_HOST}/api/generate",
                           json={"model": model, "prompt": prompt, "stream": True},
                           stream=True, timeout=timeout) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("response", "")
                if piece:
                    yield piece
                if chunk.get("done"):
                    break
    except (requests.RequestException, ValueError) as e:
        raise ModelError(f"stream() failed for {model}: {e}") from e
