# AxiomOS-Justicar

©2026 Eli pruett. All rights reserved.
This software and associated documentation may not be used, copied, modified, distributed, or sublicensed without express written permission from the author.

## Legal Notice

AxiomOS-Justicar is the original work of Eli Pruett and is protected under copyright law.

This project is not open source and does not grant any usage rights.

Any access to this repository or its contents does not constitute a license.

All rights are reserved unless explicitly granted in writing by the author.

## No Implied Rights

Nothing in this repository grants any rights to use, modify, or distribute the code or associated materials.

All rights must be explicitly granted in a separate written agreement signed by the author.




AxiomOS-Justicar: Model Architecture Specification
Document date: December 2, 2025
Core Architecture: Fully Connected Agent Mesh
The system uses a fully connected mesh topology where every agent node communicates bidirectionally with every other node. No single point of failure, no hierarchical bottleneck.
Agent Nodes
Node
Parameters
Function
3BM
3B
Memory
3BR
3B
Reason
3BC
3B
Code
8BM
8B
Memory
8BR
8B
Reason
8BC
8B
Code
14BM
14B
Memory
14BR
14B
Reason
14BC
14B
Code
9BF
9B
Face (orchestration)
Design Principle
Each functional role (Memory, Reason, Code) is instantiated at multiple parameter scales (3B, 8B, 14B), allowing the system to route tasks to the appropriate depth of processing. The 9BF node appears to serve as the orchestration layer.



~/Irwin/
│
├── axiom/                 # Constitutional + governance layer
│   ├── core.md
│   ├── ethics.md
│   ├── identity.md
│   ├── rules.md
│   └── versioning/
│
├── bin/                   # CLI entry points + system commands
│   ├── qs
│   ├── irwin
│   ├── ia
│   ├── idoc
│   ├── isearch
│   ├── ikg
│   ├── teach
│   └── utils/
│
├── core/                  # Core runtime logic (routing, bootstrap)
│   ├── router/
│   ├── runtime/
│   ├── boot/
│   └── config/
│
├── tools/                 # System tools (generated + maintained)
│   ├── ikn.sh              # (BROKEN / missing in your current state)
│   ├── ise.sh              # (BROKEN / missing)
│   ├── codegen/
│   └── helpers/
│
├── engines/               # Major system engines
│   ├── doc_engine/         # idoc
│   ├── index_engine/       # isearch backend
│   ├── kg_engine/          # ikg (CURRENTLY BROKEN - missing file)
│   │   └── engine/
│   │       └── kg_engine.py   ❌ missing in your live system
│   ├── planner/
│   ├── academy/
│   └── automation_engine/  # ia
│
├── docs/                  # Human-readable outputs
│   ├── projects/
│   ├── outlines/
│   ├── summaries/
│   └── specs/
│
├── lessons/               # Academy system content
│   ├── coding/
│   ├── math/
│   ├── languages/
│   └── engineering/
│
├── logs/                  # System + execution logs
│   ├── system/
│   ├── tasks/
│   ├── errors/
│   └── audit/
│
├── index/                 # Search + KG data layer
│   ├── data/
│   │   ├── fulltext_index.tsv
│   │   └── kg/
│   └── rebuild/
│
├── kg/                    # Knowledge graph system (BROKEN STATE)
│   ├── nodes/
│   ├── edges/
│   └── engine/            # ❌ incomplete / missing engine file
│
├── models/                # Local LLMs (GGUF + HF staged)
│   ├── 1.5b/
│   ├── 3b/
│   ├── 7b/
│   ├── 13b/
│   ├── 14b/
│   └── routing/
│
├── ollama/                # Runtime model layer
│
├── sandbox/               # TEST LAKE (HAZMAT / experimental)
│   ├── philosophy/
│   ├── ethics/
│   ├── psychology/
│   ├── red_team/
│   ├── blue_team/
│   └── purple_team/
│
├── state/                 # System configuration + sync control
│   ├── github_sources.conf
│   ├── mastodon_sources.conf
│   ├── system_state.json
│   └── routing.json
│
├── sources/               # External sync ingestion
│   ├── github/
│   └── mastodon/
│
├── teacher/               # Academy backend engine
│
├── scripts/               # Utility scripts
│
├── build/                 # Build system outputs
│
├── venv/                  # Python environment
│
└── irwin-up               # Main bootstrap launcher (conceptual entry point)




IRWINOS — SSD PORTABLE BOOT ARCHITECTURE (v1)
(Offline-first, host-agnostic AI operating system design)
🧭 1. CORE DESIGN GOAL
IrwinOS is a:
Self-contained portable AI operating system that runs entirely from a single SSD, independent of host machine state.
Key requirements:
Works on Mac / Linux / Windows via VM or native Linux boot
No dependency on cloud services
Same behavior across machines
Fully reproducible environment
Modular AI + tooling stack (Irwin engines)
Safe separation between system / models / data / experiments
💾 2. SSD PHYSICAL LAYOUT (ROOT STRUCTURE)

IRWIN_SSD/
│
├── boot/
│   ├── grub/ or systemd-boot/
│   ├── kernel/
│   └── initrd/
│
├── irwin_os/              # Core OS layer
│   ├── rootfs/
│   ├── usr/
│   ├── bin/
│   ├── etc/
│   └── lib/
│
├── irwin/
│   ├── core/              # Axiom + runtime rules
│   ├── tools/             # CLI tools (ia, idoc, ikg, etc.)
│   ├── engines/           # Irwin engines (KG, index, planner)
│   ├── sandbox/           # Test environments (HAZMAT)
│   ├── docs/
│   ├── logs/
│   ├── state/
│   └── config/
│
├── models/
│   ├── 1.5b/
│   ├── 3b/
│   ├── 7b/
│   ├── 13b/
│   ├── 14b/
│   └── embeddings/
│
├── runtime/
│   ├── ollama/
│   ├── llama.cpp/
│   ├── python_env/
│   └── node_env/
│
├── lakes/
│   ├── prod_lake/
│   ├── test_lake/
│   └── quarantine_lake/
│
├── index/
│   ├── fulltext/
│   ├── vector_db/
│   └── kg_graph/
│
└── sync/
    ├── github/
    ├── mastodon/
    └── remote_state/
🧠 3. BOOT FLOW (HOW IRWIN STARTS)
STEP 1 — SSD DETECTION
Detect bootable Irwin SSD
Identify mode:
Native Linux boot OR
VM boot (UTM/QEMU/VirtualBox)
STEP 2 — BASE OS INIT
Minimal Linux loads:
mounts SSD root
mounts /irwin/
mounts /models/
mounts /index/
STEP 3 — IRWIN BOOTSTRAP SERVICE
Launch:

/irwin/core/bootstrap.sh
Responsibilities:
load Axiom Core rules
initialize Irwin runtime
verify toolchain integrity
check model availability
validate sandbox isolation
load configuration state
STEP 4 — MODEL ROUTER STARTUP

/irwin/engines/router/
Responsibilities:
detect available models
assign tasks by tier:
Task Type
Model Tier
simple chat
1.5B–3B
reasoning
7B
planning
7B–13B
complex builds
13B–14B
codegen (restricted)
7B–13B (never max by default)
STEP 5 — ENGINE INITIALIZATION
Start in dependency order:
Index Engine
Knowledge Graph Engine
Doc Engine
Planner Engine
Task Engine (IA)
Sandbox Engine (isolated mount namespace)
STEP 6 — USER SHELL (IRWIN CLI)
User enters:

irwin
Launches unified CLI:
chat
teach
idoc
ikg
isearch
ia
sandbox tools
model switcher
system status
🔁 4. SYSTEM ISOLATION MODEL
IrwinOS enforces 3 strict data planes:
🟢 PROD LANE
stable tools
real outputs
trusted knowledge graph
safe models
🟡 TEST LAKE
experimental builds
unfinished engines
sandboxed AI experiments
philosophy + psychology lab
red/blue/purple training
🔴 QUARANTINE LANE
broken tools
failed builds
unsafe outputs
rollback zone
🧱 5. ENGINE LAYER ARCHITECTURE
Each engine is independent module:
📘 DOC ENGINE
creates structured notes
stores /docs
generates summaries
🔍 INDEX ENGINE
full-text search
global memory retrieval
cross-file linking
🧠 KG ENGINE
concept graph builder
relationship mapping
semantic linking
🧭 PLANNER ENGINE
decomposes tasks
assigns model tiers
builds execution plan
⚙️ IA (AUTOMATION ENGINE)
task runner
sync system
scheduled jobs
reindex triggers
🧪 SANDBOX ENGINE
isolated execution
no prod access
HAZMAT-safe environments
🧠 6. MODEL ECOSYSTEM
Local-only model stack:
1.5B → fast utility reasoning
3B → lightweight chat + parsing
7B → main reasoning + coding assistant
13B → deep reasoning + planning
14B → heavy analysis / synthesis
RULE:
models NEVER auto-escalate without router approval
sandbox = lowest model only unless explicitly allowed
🔐 7. SECURITY + Axiom LAYER
Always active:
identity separation (QS vs private context)
sandbox isolation enforcement
tool execution gating
file write confirmation layer
model escalation checks
no cross-lake contamination
🧩 8. PORTABILITY DESIGN RULES
IrwinOS must:
run from single SSD
not depend on host OS paths
auto-detect hardware environment
use relative mounts only
store all config inside /irwin/state
survive full machine swap
🧠 9. COGNITIVE DESIGN PRINCIPLE
IrwinOS behaves like:
“A structured thinking environment, not a chatbot system.”
Meaning:
everything becomes a tool or engine
everything is traceable
everything is reversible
everything is layered
🧭 10. FINAL BOOT STATE
When fully loaded:
User sees:

IRWIN OS ONLINE
- Models loaded
- Engines active
- Index synced
- KG online
- Sandbox isolated
- Axiom Core enforced
Then CLI becomes active.
⭐ SUMMARY
IrwinOS SSD architecture is:
Portable
Modular
Fully offline
Multi-model routed
Engine-based (not monolithic)
Sandbox-separated
Governance-layer protected
Fully reproducible across machines
