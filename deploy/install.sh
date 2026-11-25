#!/usr/bin/env bash
# AxiomOS v0.1 installer — turns a fresh Ubuntu/Debian machine (or VM) into a
# machine that boots into the governed AI shell.
#
#   sudo ./deploy/install.sh                         # find Ollama automatically
#   sudo ./deploy/install.sh http://192.168.122.1:11434   # or say where it is
#
# What it sets up, and what the OS (not just the gate) enforces:
#   /opt/axiomos              the code, owned by root: the AI user cannot edit the
#                             gate, the ledger code or the constitution (Art. 7.6)
#   user "axiom"              an ordinary, non-sudo user whose login shell is the
#                             AI shell; it can only write inside its own home
#   /var/lib/axiomos/ledger   the ledger: the AI user can append, but the anchor is
#                             root-owned in a sticky folder, so it can't be deleted
#                             or replaced — a rewritten history is detected
#   axiom-watchdog.timer      root checks the ledger every minute and advances the
#                             anchor; entries newer than the last check are not yet
#                             protected, so the exposed window is about a minute
#
# Safe to run again: it updates the code and keeps users, profiles and the ledger.
set -euo pipefail

AI_USER="${AXIOM_USER:-axiom}"
PREFIX=/opt/axiomos
STATE=/var/lib/axiomos
LEDGER_DIR="$STATE/ledger"
ENV_FILE=/etc/axiomos.env
SHELL_BIN=/usr/local/bin/axiom-shell
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this with sudo: sudo $0"
[ -d "$REPO_DIR/src/core" ] || die "can't find src/core next to this script (looked in $REPO_DIR)"
command -v apt-get >/dev/null || die "this installer needs Ubuntu or Debian (apt-get)"

# --- 1. packages ---------------------------------------------------------------
say "Installing packages (python3, venv, firejail, curl)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv firejail curl iproute2 >/dev/null

# --- 2. find Ollama -------------------------------------------------------------
say "Looking for Ollama"
OLLAMA="${1:-}"
if [ -z "$OLLAMA" ]; then
    if curl -sf -m 3 http://localhost:11434/api/tags >/dev/null; then
        OLLAMA="http://localhost:11434"
    else
        GW="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
        OLLAMA="http://${GW:-192.168.122.1}:11434"     # in a VM, the host is the gateway
    fi
fi
if curl -sf -m 5 "$OLLAMA/api/tags" >/dev/null; then
    echo "Using Ollama at $OLLAMA"
else
    warn "Ollama did not answer at $OLLAMA. Installing anyway; fix AXIOM_OLLAMA_HOST in $ENV_FILE later."
fi

# --- 3. the AI user -----------------------------------------------------------
say "Creating the '$AI_USER' user"
if id "$AI_USER" >/dev/null 2>&1; then
    echo "'$AI_USER' already exists"
else
    useradd --create-home --shell /bin/bash "$AI_USER"
fi
AI_HOME="$(getent passwd "$AI_USER" | cut -d: -f6)"

# --- 4. the code, read-only to the AI user ------------------------------------
say "Installing code to $PREFIX (owned by root)"
mkdir -p "$PREFIX"
rm -rf "$PREFIX/src"
cp -r "$REPO_DIR/src" "$PREFIX/src"
rm -rf "$PREFIX/src/mastery/my_code" "$PREFIX/src/mastery/mastery_v3.json"
find "$PREFIX/src" -name '__pycache__' -type d -prune -exec rm -rf {} +
[ -x "$PREFIX/venv/bin/python" ] || python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install -q --upgrade requests ddgs
"$PREFIX/venv/bin/python" -m compileall -q "$PREFIX/src" >/dev/null || true
chown -R root:root "$PREFIX"
chmod -R u+rwX,go+rX,go-w "$PREFIX"

# --- 5. the ledger ------------------------------------------------------------
say "Setting up the ledger in $LEDGER_DIR"
# Sticky + group-writable: the AI user can create and append its own files here,
# but can't delete or replace files root owns (the anchor).
install -d -o root -g root -m 0755 "$STATE"
install -d -o root -g "$AI_USER" -m 1770 "$LEDGER_DIR"
for f in axiom_ledger.jsonl axiom_ledger.jsonl.lock; do
    [ -e "$LEDGER_DIR/$f" ] || install -o "$AI_USER" -g "$AI_USER" -m 0640 /dev/null "$LEDGER_DIR/$f"
done

cat > "$ENV_FILE" <<EOF
# AxiomOS settings, read by the AI shell and the watchdog.
AXIOM_OLLAMA_HOST=$OLLAMA
AXIOM_LEDGER_DIR=$LEDGER_DIR
PYTHONPATH=$PREFIX/src
PYTHONDONTWRITEBYTECODE=1
EOF
chmod 0644 "$ENV_FILE"

run_py() {  # run python from the install, as root, with the AxiomOS settings
    (set -a; . "$ENV_FILE"; set +a; cd "$PREFIX/src" && "$PREFIX/venv/bin/python" "$@")
}
if [ ! -s "$LEDGER_DIR/axiom_ledger.jsonl" ]; then
    run_py -c "from core.axiom_ledger import write_entry; write_entry('AxiomOS installed', 'installer', 'allowed', reasoning='first entry, written by deploy/install.sh')"
fi
VERDICT="$(run_py -c "from core import axiom_ledger as l; print(l.verify_chain())")"
if [ "$VERDICT" = "CHAIN VALID" ]; then
    run_py -c "from core import axiom_ledger as l; c,h = l.update_anchor(); print(f'anchor: {c} entries, head {h}')"
    chmod 0644 "$LEDGER_DIR/axiom_ledger.jsonl.anchor"
else
    warn "existing ledger did not verify ($VERDICT); anchor left unchanged — investigate before trusting it"
fi

# --- 6. the AI shell ----------------------------------------------------------
say "Installing the AI shell ($SHELL_BIN)"
cat > "$SHELL_BIN" <<EOF
#!/usr/bin/env bash
# AxiomOS login shell. Commands run by other programs (ssh host 'cmd', scp)
# are handed to bash so they keep working.
if [ "\${1:-}" = "-c" ]; then exec /bin/bash "\$@"; fi

set -a; . $ENV_FILE; set +a
export AXIOM_PROJECT_ROOT="\$HOME"                     # writes stay in your home
export AXIOM_READABLE_ROOTS="\$HOME:$PREFIX/src"        # reads: home + the code
export AXIOM_MASTERY_DIR="\$HOME/.mastery"              # your learner profile
mkdir -p "\$AXIOM_MASTERY_DIR"
cd "\$HOME"
PY=$PREFIX/venv/bin/python

while true; do
    echo
    echo "AxiomOS — every action passes the constitutional gate."
    echo "  [Enter] talk to the agent   t = Mastery tutor   s = normal shell   q = log out"
    read -r -p "> " choice || exit 0
    case "\$choice" in
        "")   \$PY -m capabilities.axiom_chat ;;
        t|T)  \$PY $PREFIX/src/mastery/tutor.py ;;
        s|S)  echo "(normal shell — type 'exit' to return to AxiomOS)"; /bin/bash -i ;;
        q|Q)  exit 0 ;;
        *)    echo "Unknown choice: \$choice" ;;
    esac
done
EOF
chmod 0755 "$SHELL_BIN"
grep -qxF "$SHELL_BIN" /etc/shells || echo "$SHELL_BIN" >> /etc/shells
chsh -s "$SHELL_BIN" "$AI_USER"

# --- 7. ledger watchdog (root, every minute) -------------------------------
say "Installing the ledger watchdog (every minute)"
cat > /etc/systemd/system/axiom-watchdog.service <<EOF
[Unit]
Description=AxiomOS ledger integrity check

[Service]
Type=oneshot
EnvironmentFile=$ENV_FILE
WorkingDirectory=$PREFIX/src
ExecStart=$PREFIX/venv/bin/python -m core.ledger_watchdog --reanchor
EOF
cat > /etc/systemd/system/axiom-watchdog.timer <<EOF
[Unit]
Description=Check the AxiomOS ledger every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
EOF
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload
    systemctl enable --now axiom-watchdog.timer >/dev/null
    echo "watchdog timer enabled (see: journalctl -u axiom-watchdog)"
else
    warn "systemd is not running here; the watchdog timer was written but not started"
fi

# --- 8. a password so the AI user can log in -----------------------------------
say "Login password for '$AI_USER'"
if passwd -S "$AI_USER" 2>/dev/null | awk '{exit ($2 == "P") ? 0 : 1}'; then
    echo "'$AI_USER' already has a password"
elif [ -t 0 ]; then
    passwd "$AI_USER"
else
    warn "no terminal to ask for a password; run: sudo passwd $AI_USER"
fi

say "Done"
cat <<EOF
Log out, then log in as '$AI_USER' to boot into the AI shell.
  - The code in $PREFIX can't be changed by '$AI_USER' (the OS enforces it).
  - Ledger: $LEDGER_DIR    Settings: $ENV_FILE
  - Your own account still has a normal shell and sudo.
EOF
