# Architecture

## System outline

```text
User goal
   ↓
Company API / coordinator
   ├─ reads company context from FalkorDB
   ├─ invokes employee agents through a bounded runtime
   └─ records plans, messages, tasks, evidence, and outcomes in FalkorDB
         ↓
Employee agents: Chief of Staff · Engineering Manager · Engineer · Knowledge Manager
         ↓
Typed tools: graph query · source lookup · task/message write · review
         ↓
FalkorDB — canonical company state and relationship graph
```

The architecture is company-wide and entity-driven. Payments release readiness is one demo workflow, not a special product mode. The coordinator selects employees and tools based on the user's goal and graph context.

## Components

### FalkorDB

Canonical store for company entities, source records, evidence-backed facts, employee work, decisions, task state, durable memories, and history. Every answer and agent action must be grounded in records retrieved from FalkorDB. New sessions load relevant prior memories and work records from the graph; prompt history is not treated as durable memory.

### Ingestion pipeline

For the MVP, read local Markdown and JSON fixtures. Parse source metadata, extract or load structured entities and facts, resolve stable IDs, and upsert nodes and relationships. Re-running import must not create duplicates. Graphify may optionally help extract code/document structure; its output must pass through the importer into FalkorDB before product queries use it.

### Agent coordinator

Runs bounded workflows for company goals and questions. It classifies intent, discovers relevant entities and employees through FalkorDB, selects suitable employee procedures and tools, records a plan when work is requested, gathers results, and checks completion criteria. Start sequentially, but keep routing data-driven so other projects and departments use the same primitives.

### Employee agent

Receives a stable employee ID, role instructions, task ID, permitted tools, and a compact context bundle retrieved from FalkorDB. Returns a typed result with claims, evidence IDs, risks, and next step. The runtime persists the result before handing off.

### Interface

Shows the goal, plan, employees, task statuses, message timeline, citations, and graph path. Make it clear how graph relationships informed the answer.

### Judge-ready demo mode

The deployed demo loads a seeded synthetic workspace and opens without login or third-party OAuth. Slack and GitHub are represented by source records with recognizable types and source links; ingestion stores them in FalkorDB. Writes during the demo create simulated connector actions in FalkorDB and are visibly labeled as simulations. Keep external connector adapters behind a common interface so live OAuth integrations can be added later without changing employee workflows.

## Data flow

```text
Fixtures → parse/validate → entity resolution → FalkorDB upsert
User goal → graph retrieval → plan stored → task/message stored
Employee result → evidence validation → result stored → answer rendered
Changed source → re-ingest → old fact superseded → new fact active → re-query
Session ends → durable result/memory stored → fresh session → memory retrieved from FalkorDB
```

The judge path must not wait on external APIs or depend on a judge’s personal accounts. Seed/reset behavior must be deterministic and restore the same workspace and sample actions.

## General goal-to-work loop

```text
Understand request → retrieve company context → clarify gaps
→ choose workflow and responsible employees → plan and assign tasks
→ gather evidence and collaborate → create or update deliverable
→ review completion criteria → persist result, sources, and status
→ respond with citations and remaining blockers
```

For question-only requests, return an evidence-backed answer without creating unnecessary work. For action requests, employees may work across connected company records: draft/update documents, create or update tasks and project artifacts, prepare decisions for review, and use permitted connectors to update source systems. Every action must link the resulting record to its goal, related entities, owner, and evidence. Report completion only after the result and status are saved and verifiable.

At session close, persist durable outcomes such as decisions, findings, task status, and reusable memories with source/evidence links. On a new session, retrieve relevant prior records based on the user’s question, entities, and employee scope. Do not rely on hidden process memory or replaying the old transcript as the persistence mechanism.

The graph is both context and coordination substrate: it helps the system discover what work is needed, who should do it, what records are affected, and what evidence supports the change. Connector-backed writes should be reflected in FalkorDB with the external record ID and sync status; graph-only drafts must be labeled as drafts until approved or published.

## Retrieval and answer generation

1. Classify questions into ownership, expertise, decision rationale, project risk, or task planning.
2. Run parameterized Cypher queries for relevant entities and connected evidence.
3. Check fact status and validity interval.
4. Pass relevant, permission-eligible evidence to the employee.
5. Require evidence IDs for factual claims.
6. Validate that each evidence ID exists in retrieved context.
7. Render citations and relationship paths from graph records, not generated citation text.

Unsupported requests return what is missing, which parts are supported, and the next information or tool required. Do not silently narrow a company-wide request to the hackathon example.

## Fact updates and freshness

When an imported source changes, compare its stable source ID and version. Mark the old fact `SUPERSEDED`, retain its history, and create or update the replacement with a new validity start and source reference. Current queries filter to active facts. Historical queries may include superseded facts and dates. The hackathon demo can trigger re-ingestion manually.

## Tenant and authorization model

For the single-company prototype, use one named graph and a fixed demo user. Include `workspace_id` on nodes where practical and pass workspace context in every query. Before production multi-tenancy, implement and test graph-per-tenant isolation and source ACL checks. Never store credentials in the graph.

## Failure handling

- If FalkorDB is unavailable, stop and report that state could not be read or saved.
- If an employee fails, mark its task `FAILED`; do not fabricate completion.
- If sources conflict, show both sources, dates, and statuses.
- If evidence cannot be validated, omit the claim or label it an unverified inference.
- Bound agent turns, tool calls, and retries.
