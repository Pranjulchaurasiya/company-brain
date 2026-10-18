# Evaluation and Demo Criteria

## Track coverage

The submission must visibly demonstrate the official Company Brain focus: knowledge from docs, tickets, and chats in one graph; ownership and expertise; decision provenance; changing knowledge; source-backed answers; and an agent that gets work done across that connected context.

## Acceptance dataset

Use a fixed fictional Payments release dataset containing a project brief and architecture decision record, a ticket describing an unresolved release risk, a chat transcript recording decision rationale and a later owner change, employee profiles with skills/reporting relationships, and old plus replacement ownership facts. Record fixture IDs and expected answers in the implementation README.

Represent the chat and issue tracker sources with familiar Slack/GitHub-style records in the synthetic dataset. Reviewers do not need accounts, OAuth, or external integrations to evaluate the product.

## Pass/fail scenarios

1. **Cross-source retrieval:** one response uses a document, ticket, and chat record, with citations for factual claims.
2. **Ownership:** current-owner query returns the newest active ownership fact and cites its source.
3. **Expertise:** query returns an employee connected through a skill or prior work and explains the graph path.
4. **Decision provenance:** answer includes decision, decision-maker/date when known, and original source excerpt.
5. **Multi-hop reasoning:** query connects project → service → risk/ticket → owner or decision.
6. **Freshness:** after re-ingestion, old fact is superseded, remains historical, and is excluded from current answers.
7. **Employee collaboration:** manager assigns an investigation; task-linked request and evidence-backed response are persisted.
8. **Abstention:** absent information yields “Not documented” and identifies the sources checked.
9. **FalkorDB centrality:** answering agents read and write canonical state in FalkorDB; they do not answer by reading fixture files directly.
10. **Review readiness:** a fresh browser session opens the seeded workspace; the main workflow starts without registration, OAuth, or manual data setup.
11. **Honest integrations:** simulated connector reads/writes are labeled as simulated and are never presented as changes to real Slack or GitHub accounts.
12. **Cross-session memory:** finish a workflow, start a new session with no prior chat history, ask a related follow-up, and retrieve the earlier finding/decision/task from FalkorDB with its original source citation.
13. **Public GitHub Ingestion (Recursive Trees):** 
    - *Automated Mocked Suite (`backend/tests/test_github_ingest.py`):* Fully verifies recursive Git tree parsing (`/git/trees/{ref}?recursive=1`), nested directory paths, `#Lstart-Lend` line locator generation, stable idempotent re-import without duplicate nodes, binary/oversized file exclusion, partial failure reporting (`INGESTION_PARTIAL`), and API rate limit resilience.
    - *Manual Live Verification:* Verified live ingestion of `https://github.com/octocat/Hello-World` without authentication, extracting source file `README` and evidence excerpt `README#L1-L1` into FalkorDB, and successfully querying it via `/api/ask`. Live imports remain subject to GitHub unauthenticated IP rate limits (60 requests/hr).
14. **Unseen Grounded Q&A:** Answering unseen, non-Payments questions using strictly retrieved FalkorDB evidence with citations resolving to stored locators.
15. **Strict Honest Abstention:** If the graph has insufficient evidence, system responds with "Not documented" and enumerates checked indices; never returns a canned Payments answer.
16. **Dynamic Employee Routing:** Employee selection varies with request context and graph skills (e.g. routing infra tasks to David Kim instead of a fixed 4-agent sequence).
17. **In-App Remediation & Accurate Verdict Badges:** When a release verdict is blocked, the deliverable badge displays "Completed with conditions" and creates a real in-app remediation task in FalkorDB, clearly distinguishing completed work from proposed external writes.

## Quality measures

- **Evidence validity:** every cited ID exists and supports the claim.
- **Current-fact accuracy:** active answers exclude superseded facts.
- **Ownership accuracy:** answer matches the expected current owner.
- **Workflow completion:** goal, plan, task, handoff, report, review, and result are linked and persisted.
- **Traceability:** each answer can be followed from claim → fact → evidence → original source.

Report the tested cases and observed results honestly; do not claim broad accuracy from a small curated dataset.

## Demo sequence

1. Show employees and the seeded company graph.
2. Ask for Payments release readiness.
3. Show Chief of Staff plan and Manager task assignment.
4. Show Engineer receiving and answering a task request.
5. Show claims with excerpts from document, ticket, and chat.
6. Open ownership and decision relationship paths.
7. Re-ingest the ownership update and show the prior fact as superseded.
8. Ask current ownership again and show the changed answer.
9. End the session, start a fresh session, and ask what the company previously decided or found.
10. Show FalkorDB restoring that memory with links to the earlier task and source evidence.
11. End on the completed deliverable and audit trail.

The judge should be able to start this sequence from the landing view, without account setup or a spoken setup explanation.

## Failure signals

- Agents chat without durable task state.
- FalkorDB is decorative while answers come from files or hard-coded strings.
- Citations are model-generated rather than resolved from stored evidence.
- Old facts remain current after an update.
- Employee roles produce indistinguishable outputs.
- The demo makes claims unsupported by its dataset.
