#!/usr/bin/env python3
"""
ledger_watchdog.py - verify the ledger's integrity and shout if it breaks.

Read-only: it NEVER writes the ledger, it only checks and alerts. Run it on a
timer (cron / systemd), or with --loop to self-schedule.

    python3 ledger_watchdog.py              # one check; exit 0 ok / 1 broken
    python3 ledger_watchdog.py --loop 300   # re-check every 300s forever
    python3 ledger_watchdog.py --reanchor   # after a CLEAN check, advance the
                                            # anchor to the current head

Exit code 1 on a break makes it easy to wire into cron (which emails on nonzero)
or a systemd timer with OnFailure=.
"""
import sys
import time
from core import axiom_ledger as ledger


def notify(message, ok):
    """Where alerts go. Default: loud stdout. Wire your own channel here for the
    BROKEN case - a Discord webhook or a push. The detection is done by code
    (ledger.verify_chain); this function only delivers the verdict."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    tag = "OK   " if ok else "!!! ALERT !!!"
    print(f"[{stamp}] {tag} {message}")
    # if not ok:
    #     import requests
    #     requests.post(YOUR_DISCORD_WEBHOOK,
    #                   json={"content": f"\U0001f6a8 LEDGER: {message}"}, timeout=10)


def check(reanchor=False):
    result = ledger.verify_chain(use_anchor=True)
    ok = (result == "CHAIN VALID")
    notify(result, ok)
    if ok and reanchor:
        count, head = ledger.update_anchor()
        notify(f"anchor advanced to {count} entries (head {head[:12]}...)", True)
    return ok


def main():
    args = sys.argv[1:]
    reanchor = "--reanchor" in args
    interval = int(args[args.index("--loop") + 1]) if "--loop" in args else None

    if interval is None:
        sys.exit(0 if check(reanchor) else 1)

    while True:
        check(reanchor)
        time.sleep(interval)


if __name__ == "__main__":
    main()
