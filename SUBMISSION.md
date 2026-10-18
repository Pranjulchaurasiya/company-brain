# WeMakeDevs Graph Hacks: FalkorDB Hackathon Submission Guide

This document contains the exact, copy-pasteable answers for every required field in the **Graph Hacks: Context for AI Agents** submission form on WeMakeDevs.

---

## Part 1 of 2: Project Details

### 1. Project title *(required)*
```text
Company Brain: Engineering Change Room
```

---

### 2. Description *(required)*
*What problem does your project solve, and who is it for?*

```text
Before shipping a major engineering change—like swapping a database or deprecating an API—engineering teams and leaders struggle with the fundamental operating question: “If we make this change, what will be affected, who owns it, who knows it, which architectural decision supports it, and what concrete work must happen next?”

Conventional AI agents fail at this because vector search only retrieves isolated text chunks without relational topology, LLMs hallucinate non-existent citation IDs, and multi-agent frameworks lose their communication traces in ephemeral Python memory.

Company Brain solves this for engineering leaders, staff engineers, and cross-functional software teams by turning FalkorDB into a company operating system and persistent message bus. A 6-role multi-agent swarm (Coordinator, Code Investigator, Ownership Agent, Knowledge Agent, Reviewer, and Execution Agent) investigates proposed changes by traversing connected services, code files, pull requests, issues, active technical owners, and architecture decision records (ADRs). Unsupported claims are rejected by an automated provenance gate, active ownership dynamically updates via fact supersession, and every investigation produces a real, accountable follow-up Task stored directly in the graph.
```

---

### 3. What track are you submitting for? *(required)*
*Select all applicable tracks (check all 3):*

- [x] **Agents That Act on Connected Data** (Track 01)
- [x] **Agent Memory and Coordination** (Track 02)
- [x] **Company Brain** (Track 03)

> **Submission Note for Form:**  
> Company Brain was engineered to comprehensively fulfill and bridge all three official hackathon tracks:
> 1. **Track 01 (Agents That Act on Connected Data):** Agents execute multi-hop Cypher traversals across code repositories, commits, PRs, issues, files, and services, generating explainable breadcrumb paths and creating verified work tasks.
> 2. **Track 02 (Agent Memory and Coordination):** FalkorDB serves as a durable agent message bus (`(:Employee)-[:SENT]->(:AgentMessage)-[:TO]->(:Employee)` and `(:AgentMessage)-[:FOR_TASK]->(:Task)`). Agents maintain cross-session episodic, semantic, and procedural memory without relying on in-memory queues.
> 3. **Track 03 (Company Brain):** Connects documents, tickets, chat transcripts, employees, teams, and architecture decisions in one unified knowledge graph, with temporal fact supersession (`SUPERSEDES`) to ensure operational freshness when ownership changes.

---

### 4. Repository *(required)*
```text
https://github.com/Pranjulchaurasiya/company-brain
```

---

### 5. Demo video *(required)*
*YouTube or Loom video demo link (public or unlisted):*

```text
https://www.loom.com/share/25e8bc95d24447d2b78a268392c646a5
```

> **Recommended 3-5 Minute Video Recording Outline:**
> - **0:00 - 0:30 (The Problem):** The "Context Wall" for AI agents—vector amnesia, fake citations, and lack of relational enterprise knowledge.
> - **0:30 - 1:15 (Architecture & 3D Topology):** Show the FalkorDB Swarm Console and 3D visual graph studio showing connected services, employees, files, and decisions.
> - **1:15 - 2:30 (Engineering Change Room Workflow):** Enter `"Replace Redis with Valkey in the Payments service."` Click **Analyze Change Impact**. Show the 6-agent swarm collaborating via FalkorDB message nodes (`TASK_ASSIGNED` -> `REVIEW_REQUEST` -> `REVIEW_RESULT` -> `TASK_COMPLETED`).
> - **2:30 - 3:15 (Canonical Impact Path & Work Output):** Highlight the canonical breadcrumb path: `Proposed Change → Payments Service → redis_client.py → PR #42 → Issue #31 → Asha Patel → ADR-0042 → Follow-up Task`. Show the newly created `Task` in FalkorDB.
> - **3:15 - 4:00 (Operational Freshness Demo):** Click **"Change owner"** button. Show Asha Patel being superseded by Marcus Chen in FalkorDB via `SUPERSEDES`. Re-run analysis to show the impact path and assigned follow-up task dynamically shift to Marcus Chen.
> - **4:00 - 4:45 (Public GitHub Ingestion):** Ingest `https://github.com/octocat/Hello-World` or `encode/httpx`. Show recursive tree parsing and explicit issue resolution extraction (`fixes #N`).
> - **4:45 - 5:00 (Conclusion):** Emphasize how FalkorDB powers true agent-ness, durable memory, and verifiable company-wide execution.

---

### 6. Live demo or deployment
```text
https://company-brain.onrender.com
```
*(If evaluating locally or in an offline environment, complete 1-click reproduction instructions are provided in the repository README: `docker run -d -p 6380:6379 falkordb/falkordb:latest`, seed with `python -m backend.ingestion.importer`, and start `uvicorn backend.main:app` — zero login, zero OAuth, 100% pre-seeded).*

---

### 7. How did you use FalkorDB in your project? *(required)*
*Tell us what technical problems you solved using FalkorDB:*

```text
In Company Brain, FalkorDB is not a decorative database or an external cache; it is the canonical operational core and communication fabric for the entire system:

1. Durable Multi-Agent Message Bus: We eliminated in-memory agent queues and direct function calls by implementing an asynchronous message bus in FalkorDB using Cypher. Agents write and read structured (:AgentMessage) nodes connected via (:Employee)-[:SENT]->(:AgentMessage)-[:TO]->(:Employee) and (:AgentMessage)-[:FOR_TASK]->(:Task). Every handoff, review request, and audit verdict is permanently recorded in the graph, providing a tamper-proof execution record across sessions.

2. Four-Tier Provenance & Honest Abstention: To eliminate LLM hallucinations, every claim made by an agent must be validated through a deterministic graph chain: Claim -> Fact -> Evidence -> Source, with stable line locators (#Lstart-Lend). Sophia Wu (Knowledge Reviewer) executes Cypher queries to verify that every cited evidence ID exists in FalkorDB. If an affected entity or decision cannot be mathematically proven through graph traversal, the agent honestly abstains with "Not documented in the company graph."

3. Operational Freshness via Fact Supersession: Enterprise data changes constantly. We solved knowledge rot using temporal validity properties (valid_from, valid_until) and (:Fact)-[:SUPERSEDES]->(:Fact) relationships. When an ownership change occurs, FalkorDB archives the historical fact while activating the new one. Downstream queries automatically filter for active facts, instantly redirecting workflow assignments without requiring model re-training or vector re-indexing.

4. Multi-Hop Impact Traversals: When assessing an engineering change, FalkorDB's linear-algebra GraphBLAS engine executes sub-2ms multi-hop traversals connecting:
(Proposed Change) -> (Service) -> (File) -> (PullRequest) -> (Issue) -> (Person) -> (Decision) -> (Task).
This delivers instant, explainable risk paths across thousands of heterogenous enterprise nodes.
```

---

### 8. Blog link
*Write a blog post about your project, the problem you solve and your learnings, and share it here. The best blog post wins Apple AirPods 5.*

```text
https://medium.com/@pranjulofficial01/building-an-autonomous-company-brain-how-we-turned-falkordb-into-a-shared-operating-system-68bee7595c16
```

---

## Part 2 of 2: Feedback

### 1. What did you like about FalkorDB? *(required)*
```text
1. Blazing GraphBLAS Performance: The sparse-matrix linear algebra engine is exceptionally fast. Multi-hop queries spanning 6+ relationship tiers across services, commits, issues, and decisions executed in under 2ms with near-zero latency overhead.
2. Redis Wire Protocol Ergonomics: By building on top of the Redis protocol, FalkorDB eliminates the heavy JVM overhead and complex connection management associated with legacy graph databases (like Neo4j). Integrating with python-falkordb was seamless, lightweight, and robust.
3. Declarative openCypher Expressiveness: Cypher syntax is remarkably clean for representing complex company topologies, provenance paths, and temporal supersession patterns without writing convoluted SQL joins or document aggregations.
4. Minimal Container Footprint: Running a full FalkorDB instance in Docker with under 50MB of RAM enabled instant local spin-up and allowed our automated test suite (51 tests) to execute in seconds against isolated graph instances.
```

---

### 2. What improvements would you like to see in FalkorDB? *(required)*
```text
1. Native Relationship/Edge Property Indexing: While node property indexing is fast, adding secondary indexing capabilities directly onto edge properties (e.g. indexing timestamps or status on :SENT, :FOR_TASK, or :SUPERSEDES relationships) would significantly accelerate high-frequency time-window queries in multi-agent message buses.
2. Built-in Graph Node TTLs / Ephemeral Expiration: Native time-to-live support on specific node labels or subgraphs (e.g., expiring temporary scratchpad memories or session locks after N seconds) would make managing short-term agent memory much cleaner without requiring cron-based Cypher cleanup scripts.
3. Enhanced JSON / Nested Document Support in Cypher: Native Cypher functions to unpack or project nested JSON array properties directly during graph traversals (similar to UNWIND on parsed JSON) would make ingesting multi-line code chunks and unstructured AST metadata even more seamless.
```
