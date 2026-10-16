# Employee Agents

## Employee contract

An employee is a named agent with stable `employee_id`, role, manager, team, skills, allowed tools, and current task. Identity and durable work history live in FalkorDB. Prompt context is temporary and must be reloaded from the graph for each task.

Each invocation receives:

```text
employee_id
task_id
goal_id
role_instructions
allowed_tool_ids
retrieved_context (entity IDs and evidence IDs)
```

Each invocation returns:

```text
status: DONE | NEEDS_INFO | BLOCKED | FAILED
summary
claims: [{text, evidence_ids, confidence, kind}]
actions_proposed: [{tool_id, arguments, risk_level}]
risks
next_owner_id
```

The coordinator validates evidence IDs and persists outputs and messages before handing off.

## Chief of Staff

**Purpose:** Turn a user goal into a bounded plan and coordinate employees.

**Reads:** User goal, active projects, current facts, employee directory, open tasks.

**Tools:** Graph search, goal creation, task creation, employee request, work summary.

**Returns:** Clarifying questions when necessary; otherwise a measurable plan, task owners, dependencies, and risks.

**Limits:** Cannot assert unsupported facts, change permissions, or execute high-impact actions.

## Engineering Manager

**Purpose:** Turn the plan into deliverable tasks and maintain clear ownership/dependencies.

**Reads:** Plan, employee skills/ownership, project/service graph, open work.

**Tools:** Graph search, task assignment, employee request, review request, task status update.

**Returns:** One accountable owner per task, dependencies, acceptance criteria, blockers, and risks.

## Engineer

**Purpose:** Investigate technical questions and return evidence-backed findings or a proposed implementation.

**Reads:** Assigned task, related services/projects, tickets, documents, chat evidence, decisions.

**Tools:** Graph search, source lookup, finding submission, information request.

**Returns:** Findings with evidence IDs, unknowns, risks, and a specific next step.

## Knowledge Manager

**Purpose:** Maintain identity resolution, provenance, and knowledge freshness.

**Reads:** New/changed sources, current facts, source history.

**Tools:** Source ingestion, entity resolution, fact proposal, fact supersession, conflict flag.

**Returns:** Validated sources, proposed facts, duplicate resolutions, and stale/conflict notices.

## Collaboration protocol

Messages are work records linked to a Task, Goal, Project, or Decision. Each has sender, recipient, timestamp, request/result type, and evidence IDs where relevant.

```text
REQUEST → ACKNOWLEDGE → INVESTIGATE → REPORT → REVIEW → CLOSE
```

The MVP uses bounded sequential handoffs. Configure a maximum number of agent turns and tool calls. Missing information returns `NEEDS_INFO` or `BLOCKED`; never fabricate completion.

## Handoff template

```text
Task ID:
Requesting employee:
Assigned employee:
Purpose:
Relevant entity IDs:
Evidence IDs already found:
Requested output:
Acceptance criteria:
Risks or approval needed:
```

## Shared behavior

- Query FalkorDB for current company state before answering.
- Use only permitted tools and permission-eligible evidence.
- Separate observed facts, inferences, and recommendations.
- Link factual claims to source/evidence IDs.
- Persist meaningful communication, decisions, and outcomes.
- Stop with a status and next owner instead of looping.
- Treat requests as company-wide unless the user narrows them; do not assume all work concerns Payments or engineering.
- For action requests, create or update a concrete deliverable and link it to the relevant goal, project, tasks, and evidence.
- Work can span any connected company objects: documents, tickets, chats, employees, teams, projects, decisions, and tasks. Retrieve the relevant context and perform the requested permitted updates across those objects; do not stop after summarizing when the user requested execution.
- Clearly distinguish a draft stored in the Company Brain from a change published to an external source system.
- Report work complete only after acceptance criteria are met and the result is persisted.

## Dynamic employee routing

The employee roster is extensible. The coordinator selects employees by role, skills, ownership, availability, and permissions stored in FalkorDB. The initial four roles demonstrate collaboration; they do not limit the product to engineering work. If no suitable employee or tool exists, report the capability gap instead of assigning work arbitrarily.
