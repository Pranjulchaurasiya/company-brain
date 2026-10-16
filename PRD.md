# Product Requirements Document

## Product

Company Brain is an AI company whose employee-agents answer questions and complete work across the company using a shared FalkorDB graph. The graph connects people, teams, projects, documents, tickets, chats, decisions, and tasks so employees can understand context and act across them.

## Hackathon target

Build for the Company Brain track: connect knowledge from documents, tickets, and chats; show ownership and expertise; trace decisions to sources; keep facts current; and answer with clear evidence. FalkorDB must be central to the agent’s context and actions.

## Target user

Any company operator who wants work done across teams and company systems: find context, identify the right owner or expert, plan and delegate work, create or update deliverables, and understand the evidence behind the result.

## Product scope: company-wide work

The product accepts questions and goals across connected company domains, not only Payments or engineering. Employees must both understand and get work done across the connected context: documents, tickets, chats, people, teams, projects, decisions, and tasks. The coordinator discovers relevant records and employees through FalkorDB, chooses a suitable workflow, delegates to employees with the required skills and permissions, and returns either an evidence-backed answer or completed work.

Supported work grows through registered employee roles and tools. Examples include researching across documents and chats; creating or updating project plans and tasks; drafting or revising documents; preparing decision briefs from evidence; identifying and contacting accountable employees; updating ticket status through an approved connector; and coordinating reviews. Each workflow defines inputs, accountable owners, permissions, completion criteria, and a persisted result. Every created or updated item links to its goal, relevant entities, and source evidence. Unsupported work is reported as a capability gap or blocker.

## Hackathon demonstration: Payments release readiness

Payments is one illustrative vertical slice used to prove the general company-wide workflow. It is demo data, not the product boundary.

The user asks:

> Prepare Payments API for the next release. Find the current owner, explain the unresolved risk and the decision behind it, then coordinate the next investigation.

The company must:

1. Read a project brief, ticket, and chat transcript ingested into FalkorDB.
2. Identify the Payments API project and current owner from linked graph records.
3. Find an unresolved risk and related decision.
4. Cite the original ticket, chat, or document for every material claim.
5. Detect that an old ownership fact was superseded and report only the current owner as current.
6. Have the Chief of Staff assign an investigation to the Engineering employee.
7. Record the task, agent messages, evidence, result, and decision in FalkorDB.
8. Return readiness, open questions, accountable owner, and source links.
9. End the session, start a fresh one, and answer a follow-up using the persisted decision, finding, or task without relying on the earlier prompt history.

## Employees in the demo

- **Chief of Staff:** clarifies the request, creates a plan, delegates, and summarizes.
- **Engineering Manager:** checks ownership/dependencies, assigns tasks, and reviews progress.
- **Engineer:** investigates linked tickets and documents, then reports evidence and recommendations.
- **Knowledge Manager:** resolves source records, tracks provenance, and flags stale or conflicting facts.

Each employee has a distinct role, tool allowlist, task-linked messages, and durable work history. The graph is the shared company memory.

## Demo data

Use a fictional company and a small fixed dataset:

- Two Markdown documents: Payments release brief and architecture decision record
- One JSON ticket containing status, assignee, and source URL
- One JSON chat transcript containing risk discussion and a later ownership change
- Four employee profiles with departments, skills, and reporting lines
- One project, one service, two decisions, and two tasks

Every record has a stable ID, source type, source URI or fixture path, author when known, timestamps, and content. Label all demo information as synthetic.

## Judge experience

The deployed demo opens directly into a preloaded workspace. Judges must be able to understand and try the product without creating an account, completing OAuth, connecting Slack/GitHub, or waiting for a long setup. Seed Slack-style messages and GitHub-style issues/PRs as synthetic source records in FalkorDB. Label them clearly as simulated connector data.

Provide one prominent starter goal and several suggested questions. The application should show the agent plan, employee handoffs, graph context, source excerpts, and completed deliverable as the workflow runs. Any demo write (such as creating a task or proposed GitHub issue) is stored as a simulated in-app action and clearly labeled; do not imply that it changed a real external account.

Live Slack and GitHub OAuth are post-hackathon integrations. Keep the data model and connector boundary ready for them, but do not put their authentication flow in the judge path.

## Judge-ready demo access

- Open directly into a preloaded synthetic workspace; no account creation, OAuth, external Slack/GitHub login, or setup walkthrough is required.
- Provide a visible “Reset demo” action to restore the known starting state.
- Make the first useful interaction obvious: suggested questions and a “Run company workflow” action are available on the landing screen.
- Show synthetic-data labeling and simulated Slack/GitHub source badges clearly. Do not imply that fixture data came from live accounts.
- Keep live Slack and GitHub integrations in the product roadmap, not on the critical path for judging.

## MVP requirements

### Required

- Ingest the defined document, ticket, and chat fixtures into FalkorDB.
- Store entities, current and historical facts, tasks, messages, and provenance in FalkorDB.
- Persist useful employee/company memories across sessions, linked to their originating task, employee, and evidence.
- Answer ownership, expertise, decision rationale, and project-risk questions using graph retrieval.
- Return evidence references and a readable relationship path.
- Distinguish current, superseded, inferred, and unknown information.
- Demonstrate employee-to-employee task delegation and response.
- Produce or update a concrete deliverable, such as a reviewed release-readiness checklist, linked to the project, owner, tasks, and evidence.
- Show that the same work model can create/update connected company records (such as a task, project artifact, or decision proposal), not only return a chat response.
- Update a source, supersede an old fact, and show the changed answer.
- Show FalkorDB-backed company state in the interface.
- Open the judging workspace directly with seeded data and no login/OAuth gate.
- Make the primary demo workflow startable in one click and show useful progress immediately.

Core components must be entity- and workflow-driven rather than hard-coded to Payments. If time allows, demonstrate a second small goal or question from another company area using the same primitives.

### Out of scope for the hackathon MVP

- Live Slack, Jira, Notion, or GitHub OAuth integrations
- Unbounded autonomous operation or unrestricted agent chat
- Many departments or a large employee roster
- Production-grade enterprise SSO and full RBAC
- General-purpose codebase graphing
- Autonomous production changes
- A complex graph editor

## User-facing answer

Show a direct readiness summary; current owner; risk and assigned next task; source title/type/URI, excerpt, and date; a concise relationship path; and conflicts or missing evidence.

## Acceptance criteria

- The demo ingests at least one document, one ticket, and one chat source into one FalkorDB graph.
- Current-owner query returns the expected employee and an evidence-backed fact.
- Decision question returns the rationale and original source.
- A multi-hop query connects project → service → risk/ticket → owner or decision.
- Superseded ownership remains historical but is never returned as current.
- At least two employees exchange a task-linked request and response; both are persisted.
- A task has one accountable owner, status, result, and evidence.
- Employees produce or update a useful deliverable linked to the relevant company entities and evidence.
- A reviewer can try the product without external account setup or a live integration.
- Missing evidence yields “Not documented,” not an invented fact.
- FalkorDB is used for canonical reads and writes throughout the workflow.
- After a fresh session, an employee retrieves a prior workflow result from FalkorDB and cites its original evidence.
- A judge can start exploring the preloaded workspace immediately without signing in or connecting an account.
- Reset restores the initial synthetic workspace and makes the demo repeatable.

## Product principle

The long-term product is a company of AI employees that plan and work together. The hackathon submission proves that idea through one complete, source-grounded company workflow.
