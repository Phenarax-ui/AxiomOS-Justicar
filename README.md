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
