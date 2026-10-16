# Building Company Brain with Antigravity

## Purpose

Use Google Antigravity as the primary development environment for implementing the complete Company Brain project. This file is the build contract for Antigravity's coding agent. Treat the other project documents as product and architecture requirements.

## Read before implementation

Read these files in order:

1. `README.md`
2. `PRD.md`
3. `ARCHITECTURE.md`
4. `DATA_MODEL.md`
5. `AGENTS.md`
6. `RULES.md`
7. `TASKS.md`
8. `EVALUATION.md`

If a requirement conflicts across files, preserve the following priorities: FalkorDB is canonical; product scope is company-wide; the judging flow is preloaded and login-free; external demo data/actions are synthetic and must be labeled; citations must resolve to stored evidence.

## Implementation instructions

- Inspect the existing repository and preserve useful code and user changes before editing.
- Implement the system incrementally in the order of `TASKS.md`.
- Keep product behavior generic and data-driven. Payments is only one demo dataset; do not hard-code workflows, queries, or agent routing to it.
- Keep FalkorDB as the canonical store for company entities, facts, sources, tasks, employee messages, decisions, and outcomes.
- Source fixtures may be read during ingestion. Answering agents must retrieve company context from FalkorDB.
- Use stable IDs, idempotent ingestion, parameterized Cypher, and workspace filters.
- Build a no-login judge experience with preloaded synthetic data. Avoid login, OAuth, account creation, external API dependencies, and long-running setup in the demo path.
- Label simulated Slack/GitHub records and simulated writes in the UI. Never imply a simulated action changed an external account.
- Use typed employee inputs/outputs and bounded agent turns, tool calls, and retries.
- Validate evidence IDs before rendering factual claims. Build citations and graph paths from database records, not model-generated citation text.
- For requested work, persist a concrete deliverable or state change, its owner, status, related entities, and evidence before reporting completion.
- Keep external integrations behind adapters so real Slack/GitHub OAuth can be added after the hackathon without rewriting employee workflows.
- Update `TASKS.md` when work is completed and update the schema/docs when implementation decisions change requirements.

## Build sequence

1. Repository and runtime skeleton
2. Persistent FalkorDB connection and schema setup
3. Synthetic fixture ingestion for docs, tickets, and chats
4. Provenance-aware graph queries
5. Bounded multi-agent workflow and persisted handoffs
6. Source-backed answers and a saved deliverable
7. Freshness/supersession demonstration
8. One-click judge experience

## Definition of done

A reviewer can open the deployed app, start the sample goal, watch employee-agents collaborate, inspect FalkorDB-backed relationships and citations, see a concrete deliverable saved, and observe an outdated fact being superseded—without logging in or connecting external accounts.

## Working style for the coding agent

- Make small, coherent changes and explain the files changed.
- Ask for clarification only when the ambiguity blocks safe implementation; otherwise follow the product and architecture documents.
- Do not add integrations, roles, or features outside the current task phase.
- Preserve source licensing and attribution when adapting third-party code.
- Before concluding a phase, summarize implementation status, known gaps, and any required manual setup for the builder. Keep judge-facing setup at zero.
