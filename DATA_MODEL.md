# FalkorDB Data Model

## Modeling approach

Use explicit labels and stable IDs. Avoid vague polymorphic relationships in application queries; use clearly named relationships for supported target types. Each mutable node includes `id`, `workspace_id`, `created_at`, and `updated_at`. Use ISO-8601 UTC timestamps and source-system IDs when available.

## Node labels

```text
Employee(id, workspace_id, name, title, status)
Team(id, workspace_id, name, purpose)
Skill(id, workspace_id, name)
Goal(id, workspace_id, title, description, status, priority, created_by)
Project(id, workspace_id, name, description, status, source_id)
Service(id, workspace_id, name, environment, status, source_id)
Task(id, workspace_id, title, description, status, priority, due_at, created_by)
Document(id, workspace_id, title, source_uri, source_version, source_updated_at)
Ticket(id, workspace_id, title, status, source_uri, source_key, source_updated_at)
ChatMessage(id, workspace_id, channel, source_uri, author_id, source_created_at, body)
Decision(id, workspace_id, question, outcome, status, decided_at)
Fact(id, workspace_id, predicate, value, status, confidence, valid_from, valid_until,
     observed_at, extraction_method)
Source(id, workspace_id, source_type, source_uri, source_key, title, author_id,
       source_created_at, source_updated_at, content_hash)
Evidence(id, workspace_id, excerpt, locator, captured_at)
AgentMessage(id, workspace_id, purpose, body, status, created_at, correlation_id)
Session(id, workspace_id, started_at, ended_at, initiated_by)
Memory(id, workspace_id, memory_type, content, created_at, valid_until, status)
Review(id, workspace_id, result, feedback, created_at)
Tool(id, workspace_id, name, risk_level)
Incident(id, workspace_id, title, severity, status, started_at)
```

`Fact` is the evidence-bearing assertion layer, such as “Asha owns Payments API.” It supports temporal validity and source citations. Each fact connects to subject and object nodes through typed relationships.

## Relationships

```text
(Employee)-[:MEMBER_OF]->(Team)
(Employee)-[:REPORTS_TO]->(Employee)
(Employee)-[:HAS_SKILL]->(Skill)
(Employee)-[:OWNS_PROJECT]->(Project)
(Employee)-[:OWNS_SERVICE]->(Service)
(Employee)-[:ASSIGNED_TO]->(Task)
(Employee)-[:KNOWS_PROJECT]->(Project)
(Employee)-[:KNOWS_SERVICE]->(Service)
(Goal)-[:DRIVES]->(Project)
(Project)-[:HAS_TASK]->(Task)
(Project)-[:USES_SERVICE]->(Service)
(Project)-[:DEPENDS_ON_PROJECT]->(Project)
(Task)-[:BLOCKED_BY_TASK]->(Task)
(Task)-[:BLOCKED_BY_INCIDENT]->(Incident)
(Document)-[:DESCRIBES_PROJECT]->(Project)
(Document)-[:DESCRIBES_SERVICE]->(Service)
(Ticket)-[:TRACKS_TASK]->(Task)
(Ticket)-[:TRACKS_INCIDENT]->(Incident)
(Ticket)-[:TRACKS_PROJECT]->(Project)
(ChatMessage)-[:MENTIONS_EMPLOYEE]->(Employee)
(ChatMessage)-[:MENTIONS_PROJECT]->(Project)
(ChatMessage)-[:MENTIONS_DECISION]->(Decision)
(Decision)-[:ABOUT_PROJECT]->(Project)
(Decision)-[:ABOUT_SERVICE]->(Service)
(Decision)-[:MADE_BY]->(Employee)
(Decision)-[:SUPPORTED_BY]->(Source)
(Incident)-[:AFFECTS]->(Service)
(Fact)-[:SUBJECT_EMPLOYEE]->(Employee)
(Fact)-[:SUBJECT_PROJECT]->(Project)
(Fact)-[:SUBJECT_SERVICE]->(Service)
(Fact)-[:OBJECT_EMPLOYEE]->(Employee)
(Fact)-[:OBJECT_TEAM]->(Team)
(Fact)-[:OBJECT_PROJECT]->(Project)
(Fact)-[:OBJECT_SERVICE]->(Service)
(Fact)-[:SUPPORTED_BY]->(Source)
(Fact)-[:EVIDENCED_BY]->(Evidence)
(Fact)-[:SUPERSEDES]->(Fact)
(Source)-[:SOURCE_DOCUMENT]->(Document)
(Source)-[:SOURCE_TICKET]->(Ticket)
(Source)-[:SOURCE_CHAT]->(ChatMessage)
(AgentMessage)-[:FROM_EMPLOYEE]->(Employee)
(AgentMessage)-[:TO_EMPLOYEE]->(Employee)
(AgentMessage)-[:ABOUT_TASK]->(Task)
(Session)-[:HAS_MESSAGE]->(AgentMessage)
(Session)-[:PRODUCED_TASK]->(Task)
(Session)-[:PRODUCED_DECISION]->(Decision)
(Memory)-[:ABOUT_EMPLOYEE]->(Employee)
(Memory)-[:ABOUT_PROJECT]->(Project)
(Memory)-[:ABOUT_SERVICE]->(Service)
(Memory)-[:LEARNED_FROM_TASK]->(Task)
(Memory)-[:SUPPORTED_BY]->(Source)
(Memory)-[:EVIDENCED_BY]->(Evidence)
(Memory)-[:SUPERSEDES]->(Memory)
(Review)-[:REVIEWS_TASK]->(Task)
(Employee)-[:CAN_USE]->(Tool)
```

For other subject/object types, add explicit relationship types as needed. Do not depend on union-label syntax to define schema behavior.

## Provenance

Every factual claim used in an answer must resolve through:

```text
Fact → Source → source URI/key
Fact → Evidence → excerpt and locator
Fact → status and validity timestamps
```

Durable memories also link to the employee or company entity they concern and to the task, source, or evidence that produced them. A memory without provenance may be used only as an unverified note, not as authoritative fact.

Store a source excerpt or stable locator such as a document heading, ticket field, or chat message ID. Do not rely on an LLM-generated citation string alone.

## Current and historical facts

- `status` is `ACTIVE`, `SUPERSEDED`, `RETRACTED`, or `UNVERIFIED`.
- A fact is current only when active, `valid_from <= now`, and `valid_until` is null or in the future.
- A replacement links to its predecessor with `SUPERSEDES`.
- Preserve old facts for audit and historical questions.

## Query and storage conventions

- Enforce uniqueness on `(workspace_id, id)` per label where supported.
- Use parameterized Cypher.
- Filter every application query by workspace.
- Make ingestion idempotent using stable source keys and deterministic IDs.
- Keep large source bodies in fixture/source storage when appropriate; graph records retain references, hashes, excerpts, and metadata.
- Keep secrets outside FalkorDB.

## MVP labels

Implement Employee, Team, Skill, Project, Service, Goal, Task, Document, Ticket, ChatMessage, Decision, Fact, Source, Evidence, AgentMessage, Session, and Memory. Add Incident, Review, and Tool only if used in the chosen flow.
