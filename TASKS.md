# Hackathon Implementation Roadmap

Build reusable company-wide primitives, then prove them through the Payments release-readiness workflow. Do not add Payments-specific branches to the coordinator, graph queries, or employee tools.

## P0 — One working graph

- [x] Create the app skeleton and environment configuration.
- [x] Run FalkorDB with persistent storage.
- [x] Add connection health check and graph initialization.
- [x] Implement parameterized query helpers and workspace filtering.
- [x] Add stable IDs and idempotent upserts for core labels.

**Exit check:** re-running imports creates no duplicate entities.

## P1 — Seed and query company knowledge

- [x] Create the fictional Payments dataset from PRD.md.
- [x] Ingest the Markdown brief and decision record.
- [x] Ingest the JSON ticket and chat transcript.
- [x] Create Source, Evidence, and Fact records with provenance.
- [x] Add active and superseded ownership facts.
- [x] Add durable Session and Memory records linked to tasks and evidence.
- [x] Implement owner, expertise, decision, and risk graph queries.

**Exit check:** all three source types are queryable through FalkorDB and every expected fact resolves to evidence.

## P2 — Employee handoff

- [x] Implement the bounded coordinator and typed employee contract.
- [x] Implement Chief of Staff goal intake and planning.
- [x] Implement Engineering Manager task creation and assignment.
- [x] Implement Engineer investigation and evidence-backed report.
- [x] Implement Knowledge Manager freshness/conflict response.
- [x] Persist tasks, agent messages, findings, and outcomes in FalkorDB.

**Exit check:** two employees exchange a task-linked request and response, persisted with evidence.

## P3 — Answers and freshness

- [x] Render answers with validated citations.
- [x] Display the graph path behind each answer.
- [x] Add source update/re-ingestion action for the demo fixture.
- [x] Supersede outdated facts while retaining history.
- [x] Re-query and show the updated current answer.

**Exit check:** old ownership is auditable but never presented as current.

- [x] Persist a useful finding or decision as memory at the end of a session.
- [x] Start a fresh session and retrieve that memory using a follow-up question.
- [x] Cite the original task and source evidence when recalling it.

**Exit check:** the follow-up succeeds without prior conversation context.

## P4 — Demo interface and pitch

- [x] Show goal, employees, plan, tasks, status, and handoff timeline.
- [x] Show source excerpts and source locations.
- [x] Show the relevant FalkorDB relationship path.
- [x] Label synthetic data and add a one-click demo reset.
- [x] Open the judge workspace directly without login or OAuth.
- [x] Add a one-click starter goal and suggested questions.
- [x] Show synthetic Slack/GitHub source records with citations and simulated-write labels.
- [x] Rehearse the workflow within the event presentation time.
- [x] Prepare fallback screenshots or video for service failures.

**Exit check:** a reviewer understands the Company Brain value without implementation explanation.

## P5 — Generality smoke check

- [x] Run a second goal or question from another company area using the same graph, retrieval, and task primitives.
- [x] Confirm employee routing uses skills, ownership, availability, and permissions rather than hard-coded Payments rules.
- [x] Save a different deliverable type and link it to its sources.

**Exit check:** Payments demonstrates the product but does not define its supported scope.

## Defer until core demo works

- [ ] Live Slack/Jira/Notion/GitHub connectors
- [ ] Login, OAuth, and customer workspace onboarding
- [ ] Parallel agent execution
- [ ] Large org chart and many roles
- [ ] General graph editing interface
- [ ] Production SSO and multi-tenant deployment
- [ ] Additional autonomous tool actions
