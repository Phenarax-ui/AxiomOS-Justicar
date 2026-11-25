#!/usr/bin/env python3
"""
explain.py - point qwen3-coder at any code file and have it broken down.

    python3 explain.py bot.py
        -> a section-by-section walkthrough of the whole file

    python3 explain.py bot.py "why does award_xp use @bot.listen not @bot.event?"
        -> answers that specific question about the file, pointing at the lines

Runs on IRWIN, where the model lives. No Discord, no tutor state - just you,
a file, and the model. This is the 'how it works' idea from the tutor, aimed
at real code: your code. The reply streams in as it's generated so you're not
staring at a blank screen while a 30b model thinks.
"""
import sys
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3-coder:30b"


def stream_model(prompt):
    """Send the prompt and print the reply as it arrives, token by token.
    Ollama streams newline-delimited JSON when stream=True; each line carries
    a 'response' piece and a 'done' flag on the last one."""
    with requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": True},
        stream=True,
        timeout=600,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            print(chunk.get("response", ""), end="", flush=True)
            if chunk.get("done"):
                break
    print()


def main():
    if len(sys.argv) < 2:
        print('usage: python3 explain.py <file> ["a specific question"]')
        return

    path = sys.argv[1]
    question = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        with open(path) as f:
            code = f.read()
    except OSError as e:
        print(f"can't read {path}: {e}")
        return

    if question:
        task = (
            f"The student has a specific question about this file.\n"
            f"Question: {question}\n\n"
            "Answer it clearly, pointing to the exact lines involved, and "
            "explain the reasoning - not just the fact."
        )
    else:
        task = (
            "Walk through this file for the person who wrote it while learning "
            "Python. Go section by section: what each part does and why it's "
            "there. Call out anything clever or worth understanding better. "
            "Be clear and useful - skip the obvious, don't pad."
        )

    prompt = (
        f"You are a patient coding tutor reading a student's Python file "
        f"named {path}.\n\n```python\n{code}\n```\n\n{task}"
    )

    print(f"asking {MODEL} about {path}...\n")
    try:
        stream_model(prompt)
    except requests.RequestException as e:
        print(f"\n[could not reach the model: {e}]")
        print("Is Ollama running on this machine? Try: ollama ps")


if __name__ == "__main__":
    main()
