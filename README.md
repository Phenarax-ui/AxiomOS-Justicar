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

