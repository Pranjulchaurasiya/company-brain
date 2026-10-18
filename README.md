# Company Brain: Engineering Change Room

> **Release Status:** Hackathon-ready, end-to-end verified prototype.  
> **Core Operating Question:**  
> *“If we make this change, what will be affected, who owns it, who knows it, which decision supports it, and what work must happen next?”*

Company Brain is a graph-backed company operating system where employee-agents investigate, communicate, verify evidence, and produce real work using a shared **FalkorDB** knowledge graph. FalkorDB is the canonical store for company knowledge, task state, messages, and memory.

Unsupported claims are rejected or returned without evidence; facts and actions require traceable graph provenance.

Agents do not communicate through hidden Python in-memory variables or direct function calls. Instead, **FalkorDB serves as their shared company workspace and message bus**. Every handoff, investigation finding, review result, and follow-up task is durably persisted and queryable in the graph.

---

## 🌐 FalkorDB Network Topology & Environment

* **Host Port:** `6380`
* **Docker Container Port:** `6379`
* **Port Mapping:** `0.0.0.0:6380 -> 6379/tcp`
* **Port Reference Guarantee:** No stale host-port references to 6379. Port 6379 remains the intentional internal FalkorDB container port, mapped to host port 6380.
* **Canonical Graph Variable:** `FALKORDB_GRAPH_NAME=company_brain` (shared across `.env.example`, `backend/config.py`, and runtime)

---

## 👥 6 Workflow Roles Across 5 Canonical Employees

The graph stores five persistent employees. Some employees perform multiple controlled workflow roles. All handoffs, findings, and state transitions remain persisted in FalkorDB:
1. **Coordinator** (`emp_chief_of_staff` — Elena Vance): Decomposes goals into investigation tasks.
2. **Code Investigator** (`emp_engineer` — Asha Patel): Traverses code repositories, commits, PRs, files, and line locators.
3. **Ownership Agent** (`emp_eng_manager` — Marcus Chen): Resolves responsible service owners and accountable teams.
4. **Knowledge Agent** (`emp_knowledge_mgr` — Sophia Wu): Retrieves governing decisions (ADRs) and architectural context.
5. **Reviewer** (`emp_knowledge_mgr` — Sophia Wu): System quality & provenance gate; audits evidence IDs and flags unproven items.
6. **Execution Agent** (`emp_chief_of_staff` / `emp_eng_manager`): Persists actionable follow-up tasks and dry-run GitHub issues.
*(Historical infrastructure engineer `emp_prior_dev` — David Kim provides legacy migration telemetry).*

---

## 🏛️ Engineering Change Room Architecture

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

### Canonical Graph Impact Path
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

If the graph cannot prove an affected entity or decision, the system honestly abstains:
> **"Not documented in the company graph."**

---

## 🚀 Working Vertical Slice Status

| Capability | Status | Implementation & Storage |
|---|---|---|
| **Engineering Change Room** | ✅ **Automated Tests + UI Verified** | Analyzes proposed changes (*"Replace Redis with Valkey in Payments"*), resolves affected services, files, PRs, issues, owners, and decisions, producing canonical breadcrumb paths. |
| **Durable FalkorDB Message Bus** | ✅ **Automated Tests + UI Verified** | Agents write and read structured `(:AgentMessage)` nodes in FalkorDB (`SENT`, `TO`, `FOR_TASK`, `SUPPORTED_BY`) with typed handoffs (`TASK_ASSIGNED`, `REVIEW_REQUEST`, `REVIEW_RESULT`, `TASK_COMPLETED`). |
| **Operational Freshness ("Change Owner")** | ✅ **Automated Tests + UI Verified** | Instant demo button toggles active technical owner between Asha Patel and Marcus Chen via fact supersession (`SUPERSEDED_BY`). Re-running analysis immediately shifts the recommended assignee. |
| **Real Work Output (Task Creation)** | ✅ **Automated Tests + UI Verified** | Generates real `(:Task)` in FalkorDB (`task_valkey_migration_review`), linked to Goal, Service, Decision, Owner, and Evidence locators. |
| **Public GitHub Ingestion (Recursive Trees)** | ✅ **Automated Mocked Tests + Live Verified** | Fetches repo metadata and recursive file tree via Git Trees API (`/git/trees/{ref}?recursive=1`). Imports bounded text/Markdown files, skipping binaries (`.png`, `.exe`, `.zip`) and oversized files (> 60KB). Stores `(:Project)-[:HAS_SOURCE]->(:Source)-[:CONTAINS_EVIDENCE]->(:Evidence)` in FalkorDB with stable IDs, line locators (`#Lstart-Lend`), and idempotent upserts. |
| **Engineering Contribution Investigator** | ✅ **Automated Mocked Tests + Live Verified** | Imports bounded GitHub repository history (commits, pull requests, issues, touched files, reviews) via public REST API. Persists canonical graph in FalkorDB (`Repository`, `Person`, `Commit`, `PullRequest`, `Issue`, `File`). Strictly creates `RESOLVES_ISSUE` relationships only when explicitly supported by closing keywords (`fixes #N`, `closes #N`). Assignee/closer are stored as metadata, never inferred as fix authors. |
| **Document / Markdown Ingestion** | ✅ **Verified Real** | Users can import Markdown/text files via UI or `POST /api/ingest/document`. Chunks text into grounded FalkorDB Evidence nodes. |
| **Grounded Graph Question Answering** | ✅ **Verified Real** | `POST /api/ask` queries FalkorDB Evidence/Source/Fact/Decision entities with honest abstention when unsupported. |
| **Dynamic Request-Driven Employee Routing** | ✅ **Verified Real** | Dynamically routes tasks to employees based on graph skills, ownership, and current goal context. |
| **Synthetic Payments Fixture** | ℹ️ **Demo Option Only** | The Payments dataset is preserved for 1-click no-login hackathon evaluation; all core endpoints operate over arbitrary ingested company context. |


---

## 🔬 Engineering Contribution Investigator: Tested vs. Manually Verified

### 1. Automated Mocked Test Suite (`backend/tests/test_contribution_investigator.py`)
7 comprehensive tests run against the isolated `company_brain_test` graph with zero external network dependencies:
- **Explicit Closing Keyword Extraction**: Tests `extract_explicit_resolved_issues` with diverse syntax patterns (`fixes #101`, `Closes: #102`, `resolved #103`, `Fixes #200 and closes #201`). Confirms assignees, mentions (`cc @alice`), and closer logins are never extracted as resolvers.
- **Canonical Graph Persistence & Authorship**: Verifies creation of `Repository`, `Person`, `Commit`, `PullRequest`, `Issue`, `File`, `AUTHORED_COMMIT`, `OPENED_PR`, `OPENED_ISSUE`, `REVIEWED_PR`, and `TOUCHED_FILE` edges.
- **Closer & Assignee Isolation**: Confirms issue `closer` (`closer_dev`) and `assignee` (`assignee_dev`) are stored purely as scalar node properties on `Issue`, and asserts that no `AUTHORED_COMMIT`, `OPENED_PR`, or `RESOLVES_ISSUE` relationships are linked to them.
- **Repeat-Import Idempotency**: Re-importing identical payloads produces 0 duplicate nodes and 0 duplicate edges across all node labels.
- **Pagination**: Bounded pagination fetches multi-page batches (e.g. pages 1 and 2) and halts when page count reaches the safety limit or returns fewer items than `per_page`.
- **Rate-Limit Resilience (HTTP 403 / 429)**: Validates that rate-limiting returns a clear structured error (`RATE_LIMIT_EXCEEDED`) without corrupting or wiping existing graph entities.
- **Read-Only Person Query**: Validates `GET /api/investigator/contributions?username={user}` returns accurate counts of authored commits, opened PRs, reviews, and explicitly linked issues.

### 2. Live Public Network Manual Verification
Manually executed against real public GitHub repositories on an isolated graph (`company_brain_manual_test`), without modifying or resetting `company_brain`:
- **Repository 1**: `https://github.com/octocat/Hello-World`
  - **Actual Records Imported**: 3 commits, 10 pull requests, 10 issues, 21 contributors, 4 files, 0 explicit resolutions.
  - **Read-Only Person Query**: Queried `octocat`:
    - 1 commit (`7fd1a60b01f91b314f59955a4e4d4e80d8edf11d` "Merge pull request #6 from Spaceghost/patch-1")
    - 0 PRs, 0 reviews, 0 explicit issues resolved.
- **Repository 2**: `https://github.com/encode/httpx`
  - **Actual Records Imported**: 10 commits, 10 pull requests, 10 issues, 28 contributors, 14 files, 1 explicit resolution.
  - **Explicit Resolution Verification**: Pull Request #3777 by `akx` contained `"Fixes #3686"` in its body. Graph correctly generated edge:
    `(:PullRequest {number: 3777})-[:RESOLVES_ISSUE]->(:Issue {number: 3686})`
  - **Read-Only Person Query**: Queried `akx`:
    - Authored Commits: 1 commit (`76c7576a917e765595c2ec8fa632ba5f8a00a12e` "Fix chunk size handling in sync streaming responses (#3777)")
    - Opened PRs: PR #3777 ("Fix chunk size handling in sync streaming responses")
    - Explicitly Resolved Issues: Issue #3686 ("Chunk size not respected in sync streaming responses") via PR #3777.

### 3. Untested Claims & Operational Boundaries
- **Explicit Resolution Boundary**: `RESOLVES_ISSUE` is created *only* when PR bodies or commit messages explicitly contain supported GitHub closing patterns (`fix`, `fixes`, `fixed`, `close`, `closes`, `closed`, `resolve`, `resolves`, `resolved`). Issues closed manually or PRs that only reference an issue conversationally without closing syntax are deliberately not linked.
- **Public Rate Limits**: GitHub's unauthenticated REST API enforces a 60 requests/hour limit per IP. An optional server-side `GITHUB_TOKEN` can be supplied in `.env` to raise this to 5,000 req/hr; tokens are never sent to the browser.
- **Safe Read-Only Slice**: This vertical slice provides pure read-only ingestion and query. No OAuth tokens, no writebacks to external GitHub repos, and no LLM reasoning are involved.

---

## 🔍 Public GitHub Ingestion: Tested vs. Manually Verified

### 1. Automated Mocked Test Suite (`backend/tests/test_github_ingest.py`)
All 10 tests run against the isolated `company_brain_test` graph with zero external network dependencies:
- **Nested Files & Tree Traversal**: Recursively retrieves multi-tier directories (`docs/architecture/rfc-009.md`, `src/gateway/router.py`, `configs/production.yaml`).
- **Text Retrieval & Evidence Locators**: Grounded chunks with `#Lstart-Lend` line locators resolving to file paths and source URIs.
- **Idempotent Re-Import**: Second import of the identical repo produces identical node and relationship counts (zero duplicate nodes).
- **Binary & Oversized Skipping**: Automatically skips binaries (`.png`, `.exe`, `.zip`) and files exceeding size threshold (> 60KB), returning clear reasons in `skipped_files`.
- **Partial Failure Handling**: If individual file downloads fail (e.g., HTTP 500), returns `INGESTION_PARTIAL`, stores successful files, and lists `files_failed` with HTTP status.
- **Rate Limit Resilience**: HTTP 403 / 429 rate limit responses return `RATE_LIMIT_EXCEEDED` without crashing or storing corrupted state.
- **Missing / Private Repositories**: HTTP 404 returns `REPO_NOT_FOUND` with clear guidance that only public repositories can be imported without OAuth.
- **Truncated Tree Responses**: Preserves `tree_truncated: true` when repository exceeds Git Trees API single-response limit (> 100k objects).

### 2. Live Public Network Manual Verification
- **Target Repository**: `https://github.com/octocat/Hello-World`
- **Result**: Successfully fetched repo metadata (default branch `master`), retrieved `README`, stored 1 Source node and 1 Evidence node (`README#L1-L1`, excerpt `"Hello World!"`).
- **Query Verification**: Queried `"Hello World greeting"` via graph retrieval; answer correctly cited `ev_src_proj_gh_octocat_hello_world_5e79b251c455_1_1_fd854d1d2228` with locator `README#L1-L1`.
- **Rate Limit Notice**: Live public GitHub API access is unauthenticated and subject to GitHub's 60 req/hr IP limit. Optional `GITHUB_TOKEN` in `.env` is supported server-side for higher limits, but is never exposed to the client.

---

## 💬 FalkorDB Agent Message Bus Specification

Unlike systems that use in-memory message queues or direct agent-to-agent Python function invocations, Company Brain agents communicate **strictly through FalkorDB**. FalkorDB is their shared persistent company workspace and message bus.

### Graph Relationship Model
```cypher
(:Employee)-[:SENT]->(:AgentMessage)
(:AgentMessage)-[:TO]->(:Employee)
(:AgentMessage)-[:FOR_TASK]->(:Task)
(:AgentMessage)-[:SUPPORTED_BY]->(:Evidence)
```

### Agent Turn Contract & Flow
1. **Chief of Staff (Coordinator)**:
   - Reads goal and graph context.
   - Creates `(:Task {title: "Investigate impact of Valkey migration in Payments"})`.
   - Writes `(:AgentMessage {message_type: 'TASK_ASSIGNED', sender_id: 'emp_chief_of_staff', receiver_id: 'emp_engineer'})`.
2. **Engineering Investigator**:
   - Reads task and previous messages from FalkorDB.
   - Follows graph traversal: `(Service) -> (File) -> (PullRequest) -> (Issue) -> (Person) -> (Decision)`.
   - Writes `(:AgentMessage {message_type: 'REVIEW_REQUEST', sender_id: 'emp_engineer', receiver_id: 'emp_knowledge_reviewer', evidence_ids: [...]})`.
3. **Knowledge Reviewer**:
   - Reads Investigator's message from FalkorDB.
   - Verifies all cited evidence IDs against active FalkorDB nodes.
   - Writes `(:AgentMessage {message_type: 'REVIEW_RESULT', sender_id: 'emp_knowledge_reviewer', receiver_id: 'emp_eng_manager', status: 'APPROVED'})`.
4. **Engineering Manager**:
   - Reads approved review from FalkorDB.
   - Creates actionable follow-up task `(:Task {title: "Review Valkey migration impact on payment retry worker"})`.
   - Assigns task to current technical owner resolved dynamically from active graph facts.
   - Writes `(:AgentMessage {message_type: 'TASK_COMPLETED', sender_id: 'emp_eng_manager', receiver_id: 'emp_chief_of_staff'})`.

---

## 🎬 10-Step Interactive Demo Walkthrough

Follow this 10-step sequence to demonstrate the complete graph-powered change-impact system:

1. **Load a Public GitHub Repository**:
   - In the FalkorDB Swarm Console, enter `https://github.com/octocat/Hello-World` or `https://github.com/encode/httpx`.
   - Click **"Ingest Repository Tree"** or **"Ingest Contributions"** to import commits, PRs, issues, changed files, and contributors directly into FalkorDB.
2. **Inspect Company Employees and Ownership**:
   - View synthetic company employees: Chief of Staff, Engineering Investigator, Knowledge Reviewer, and Engineering Manager.
   - Note that external GitHub users (`octocat`, `akx`) are imported strictly as external contributors (`Person`), kept cleanly separate from internal company employees (`Employee`).
3. **Enter a Proposed Engineering Change**:
   - In the **Engineering Change Room** card, enter:
     `"Replace Redis with Valkey in the Payments service."`
   - Notice the current owner badge displays `Owner: Asha Patel`.
4. **Coordinator Creates the Plan**:
   - Click **"Analyze Change Impact"**.
   - Coordinator (`Chief of Staff`) creates a Goal and assigns investigation to `Engineering Investigator` via a `TASK_ASSIGNED` message written to FalkorDB.
5. **Investigator Follows Graph Paths**:
   - Investigator traverses FalkorDB code and provenance paths, locating `svc_payments_settlement`, `redis_client.py`, `PR #42`, `Issue #31`, `Asha Patel`, and `ADR-0042`.
   - Investigator posts `REVIEW_REQUEST` to the FalkorDB message bus with evidence citations.
6. **Reviewer Validates Citations**:
   - Knowledge Reviewer inspects all cited evidence IDs against the graph.
   - Emits `REVIEW_RESULT` with `APPROVED` status back to FalkorDB.
7. **Company Brain Shows Impact, Owners, Decisions, and Risks**:
   - UI renders the **Canonical Graph Impact Path**:
     `Proposed Change → Payments Service → redis_client.py → PR #42 → Issue #31 → Asha Patel → ADR-0042 → Follow-up Task`.
   - Displays affected files, architecture decisions, and reviewer requirements.
8. **Follow-Up Task Created in FalkorDB**:
   - Work output card displays newly generated task:
     `"Review Valkey migration impact on payment retry worker"`, assigned to **Asha Patel** with priority `HIGH`.
9. **Change an Ownership Fact**:
   - Click the demo button **"Change owner"**.
   - An operational fact supersession occurs in FalkorDB: Marcus Chen is recorded as the active owner, superseding Asha Patel.
   - The badge updates to `Owner: Marcus Chen`.
10. **Re-Run and Verify Dynamic Result Change**:
    - Click **"Analyze Change Impact"** again.
    - Notice the Canonical Impact Path and the created follow-up task now designate **Marcus Chen** as the assignee.
    - This conclusively proves the graph is **live operational state**, not hardcoded static decoration!

---

## 🛠️ Quickstart

### 1. Requirements
- Python 3.11+
- Docker Desktop with FalkorDB container

```powershell
# Check whether the container already exists
docker ps -a --filter "name=company_brain_falkordb"

# If it exists:
docker start company_brain_falkordb

# If it does not exist, create it:
docker run -d --name company_brain_falkordb `
  -p 6380:6379 `
  -v falkordb_data:/var/lib/falkordb/data `
  falkordb/falkordb:latest
```

### 2. Setup & Ingestion
```bash
# Activate virtual environment
.venv\Scripts\activate

# Seed initial benchmark fixtures into FalkorDB
.venv\Scripts\python -m backend.ingestion.importer

# Launch backend
.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` in your browser.

### 3. Run Acceptance Tests (Isolated Test Graph)
Acceptance tests run strictly against an isolated test graph (`company_brain_test`), ensuring the live `company_brain` graph is never reset or modified. All 51 tests pass:
```bash
# Run Engineering Change Room tests
pytest backend/tests/test_change_room.py -v

# Run full test suite (51 tests covering Change Room, Contribution Investigator, Tree Ingestion, Routing, Freshness)
pytest backend/tests/ -v
```

---

## 📚 Architectural Documents
- [PRD.md](PRD.md) — product scope and requirements
- [ARCHITECTURE.md](ARCHITECTURE.md) — system design
- [DATA_MODEL.md](DATA_MODEL.md) — FalkorDB graph schema
- [AGENTS.md](AGENTS.md) — employee roles and collaboration protocol
- [RULES.md](RULES.md) — safety and operating rules
- [EVALUATION.md](EVALUATION.md) — quality and evaluation criteria
- [BUILDING_WITH_ANTIGRAVITY.md](BUILDING_WITH_ANTIGRAVITY.md) — build workflow and coding-agent instructions
