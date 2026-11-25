"""
core/config.py — single source of truth for models, endpoints, and path policy.

Change a value here and every module picks it up. No more hand-syncing the same
model tag across code_agent, spec_agent, axiom_chat, the gate and the dispatcher
(the thing that bit us when code_agent moved to qwen3-coder and spec_agent had to
follow by hand). Same idea as constitution.py — define once, import everywhere.

Modules keep their own local names and just source the value, e.g.:
    from core import config
    MODEL = config.CODER_MODEL

NOT centralized here, on purpose:
  * the ledger's file paths — axiom_ledger.py self-locates them next to itself
    (correct no matter which directory you run from), so they don't belong here.
  * the gate's secret-file name/dir/ext lists — security constants tightly bound
    to the gate's own logic, not deployment config.
"""

# --- Ollama endpoint --------------------------------------------------------
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_CHAT = OLLAMA_HOST + "/api/chat"

# --- model tags (keep these matching your `ollama list`) --------------------
GATE_MODEL   = "qwen3:4b"          # axiom_gate: the small constitutional judge
CODER_MODEL  = "qwen3-coder:30b"   # code_agent + spec_agent: write & spec code
CHAT_MODEL   = "gpt-oss:20b"       # axiom_chat: the conversational agent
ROUTER_MODEL = "qwen3:14b"         # dispatcher: plain-language routing

# --- path policy ------------------------------------------------------------
PROJECT_ROOT   = "/home/phenarax"             # writes/exec confined under here
READABLE_ROOTS = (                            # reads confined to these (default-deny)
    "/home/phenarax/axiom",
    "/home/phenarax/mastery",
    "/home/phenarax/bounty",
)
BOUNTY_DB_PATH = "bounty.db"                   # scope data (programs, scope_items)
