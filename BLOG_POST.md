# Building an Autonomous Company Brain: How We Turned FalkorDB Into a Shared Operating System & Message Bus for AI Agents

> **"If we make this change, what will be affected, who owns it, who knows it, which architectural decision supports it, and what concrete work must happen next?"**

Every engineering leader and developer has faced this fundamental question before deploying a breaking change, deprecating a service, or swapping a critical infrastructure dependency. In traditional organizations, the answer is scattered across outdated Confluence docs, abandoned Jira tickets, ephemeral Slack threads, and tribal knowledge trapped in senior engineers' heads.

When teams try to solve this with conventional AI agents, they quickly run into the **Context Wall**:
1. **Stateless Vector Amnesia**: Vector search retrieves chunks by semantic similarity, not relational topology. An agent can't reliably traverse from a code file to the pull request that introduced it, the ticket that justified it, the engineer who owns it, and the architecture decision record (ADR) that governs it.
2. **Hallucinated Citations**: LLMs generate plausible-sounding explanations and hallucinate citation IDs that don't exist in the company's real records.
3. **Black-Box In-Memory Agents**: Multi-agent frameworks (LangGraph, CrewAI, AutoGen) pass state through temporary Python memory or ephemeral JSON blobs. If an agent crashes or finishes its turn, its reasoning trace and handoffs disappear into the void.

To solve this, we built **Company Brain: Engineering Change Room** for the **Graph Hacks Hackathon by WeMakeDevs & FalkorDB**. 

Instead of treating the graph as a passive visualization or a secondary sidecar, **FalkorDB is the canonical operating system and durable message bus for our entire multi-agent swarm**.

---

## 🏗️ Architectural Paradigm: The Graph is the Company Operating System

At the heart of Company Brain is a fundamental design rule:
> **If the product still works when FalkorDB is taken out, the graph is decoration. In Company Brain, agents cannot communicate, investigate, or verify claims without FalkorDB.**

Agents do not call each other directly or exchange hidden Python state. Instead, every agent turn is a persisted graph transaction:

```text
User Proposes Change: "Replace Redis with Valkey in the Payments service."
       ↓
Coordinator (Chief of Staff) creates Goal & Task in FalkorDB
       ↓ (FalkorDB AgentMessage: TASK_ASSIGNED)
Impact Investigator reads task from FalkorDB, traverses code & graph paths
       ↓ (FalkorDB AgentMessage: REVIEW_REQUEST with cited evidence)
Knowledge Reviewer validates all claims & citations against FalkorDB
       ↓ (FalkorDB AgentMessage: REVIEW_RESULT)
Coordinator / Engineering Manager creates actionable Follow-up Work Task in FalkorDB
       ↓
User Receives Canonical Impact Path + Real Work Task + Verifiable Citations
```

### The FalkorDB Durable Message Bus

We modeled multi-agent communication directly into the graph schema:

```cypher
(:Employee)-[:SENT]->(:AgentMessage)
(:AgentMessage)-[:TO]->(:Employee)
(:AgentMessage)-[:FOR_TASK]->(:Task)
(:AgentMessage)-[:SUPPORTED_BY]->(:Evidence)
```

When Elena Vance (Chief of Staff) assigns an investigation to Asha Patel (Engineering Investigator), she executes an idempotent Cypher `MERGE` that creates an `(:AgentMessage {message_type: 'TASK_ASSIGNED'})` node linked to the target `(:Task)`. 

When Asha finishes inspecting the codebase, she posts a `REVIEW_REQUEST` message linked to the exact `(:Evidence)` nodes she discovered. Sophia Wu (Knowledge Reviewer) queries the graph for unread messages addressed to her, validates every cited evidence ID against active nodes in FalkorDB, and writes back an `APPROVED` or `REJECTED` `REVIEW_RESULT`.

Because messages are first-class graph nodes, any session can inspect the full historical audit trail across all agents, long after the original API call has completed.

---

## 🔬 The Canonical Graph Impact Path

When a user submits a proposed change—such as *"Replace Redis with Valkey in the Payments service"*—the agent swarm traverses a multi-hop graph path across heterogenous corporate artifacts:

```text
Proposed Change
  → Payments Service (svc_payments_settlement)
  → redis_client.py (file_payments_redis_client)
  → PR #42 ("Migrate session store and retry cache to Redis")
  → Issue #31 ("Spike: evaluate in-memory key-value cache")
  → Asha Patel (Owner / Technical Lead)
  → ADR-0042 ("Adopt Redis for high-throughput distributed caching")
  → Follow-up Task ("Review Valkey migration impact on payment retry worker")
```

Every claim in the generated deliverable is grounded in a four-tier provenance chain:
$$\text{Claim} \longrightarrow \text{Fact} \longrightarrow \text{Evidence} \longrightarrow \text{Source}$$

If an entity, owner, or architectural decision is not provable in the graph, the system honestly abstains:
> **"Not documented in the company graph."**

---

## ⚡ The Operational Freshness Guarantee: Dynamic Fact Supersession

Static databases quickly rot when team ownership shifts. Company Brain implements temporal fact supersession in FalkorDB using `valid_from`, `valid_until`, and `SUPERSEDES` relationships:

```cypher
// Superseding an old ownership fact with a new active fact
MATCH (old_fact:Fact {id: $old_fact_id})
SET old_fact.status = 'SUPERSEDED', old_fact.valid_until = $now
CREATE (new_fact:Fact {
    id: $new_fact_id,
    predicate: 'OWNS_PROJECT',
    status: 'ACTIVE',
    valid_from: $now,
    valid_until: null
})
CREATE (new_fact)-[:SUPERSEDES]->(old_fact)
CREATE (new_fact)-[:SUBJECT_PROJECT]->(p)
CREATE (new_fact)-[:OBJECT_EMPLOYEE]->(new_owner)
```

In our live interactive console, clicking the **"Change owner"** demo button supersedes Asha Patel's ownership of the Payments service and assigns Marcus Chen as the new active owner. When the user re-runs *"Analyze Change Impact"*, the generated impact path and follow-up work task instantly designate Marcus Chen as the assignee.

This conclusively proves to judges and developers that FalkorDB is live operational state, not hardcoded mock data.

---

## 🌐 Public GitHub Ingestion & Contribution Investigator

In addition to synthetic company fixtures for instant 1-click evaluation, Company Brain includes two live public GitHub ingestion engines:

1. **Recursive Tree Ingestion (`/git/trees/{ref}?recursive=1`)**:
   Recursively imports repositories (e.g. `octocat/Hello-World` or `encode/httpx`), generating stable line locators (`#Lstart-Lend`) and chunked `Evidence` nodes in FalkorDB while automatically skipping binaries (`.png`, `.exe`, `.zip`) and oversized files (> 60KB).
2. **Engineering Contribution Investigator**:
   Imports commits, PRs, issues, touched files, and reviews. Strictly creates `RESOLVES_ISSUE` relationships only when explicitly supported by standard GitHub closing keywords (`fixes #101`, `closes #102`). Assignees and closers are preserved strictly as scalar properties, preventing false resolution inferences.

---

## 💡 Learnings & Feedback on FalkorDB

Building Company Brain with FalkorDB provided several critical engineering takeaways:

### What We Loved:
- **Blazing Execution Speed**: FalkorDB's GraphBLAS sparse matrix linear algebra engine delivers sub-millisecond graph traversals. Multi-hop queries spanning 6+ relationship hops executed in under 2ms.
- **Redis Protocol Ergonomics**: Using the familiar Redis wire protocol and client libraries made integration trivial. No heavy JVM dependencies or clunky connection pools.
- **Native Cypher Support**: Declarative openCypher syntax made expressing complex graph traversals (`MATCH (p)-[:USES_SERVICE]->(s)...`) intuitive and clean.
- **Resource Efficiency**: A full container footprint under 50MB RAM allowed us to run complete isolated test suites with 51 passing tests in seconds.

### Improvements We'd Love to See:
1. **Dynamic Edge Property Indexing**: Enhanced secondary indexing over relationship properties would accelerate time-windowed traversals on high-throughput message graphs.
2. **Native JSON Path Unnesting**: While FalkorDB handles scalar node properties elegantly, native unnesting of nested JSON lists in Cypher projection would streamline document chunking pipelines.
3. **Built-in Ephemeral Graph TTLs**: Native time-to-live expiration on specific node labels (e.g. temporary scratchpad memories or session locks) would simplify cache hygiene in agent swarms.

---

## 🏆 Conclusion: The Future of Agentic Work is Graph-Native

Agents cannot collaborate on complex real-world tasks with flat text files and probabilistic vectors alone. By giving our agent swarm a structured, persistent, and verifiable memory layer in **FalkorDB**, we transformed chaotic multi-agent communication into a deterministic company brain where every decision is traceable, every claim is proven, and every action produces real, accountable work.

- **GitHub Repository**: [https://github.com/Pranjulchaurasiya/company-brain](https://github.com/Pranjulchaurasiya/company-brain)
- **Live Demo & Docs**: Included in repository README
- **Built for**: Graph Hacks Hackathon (WeMakeDevs & FalkorDB)
