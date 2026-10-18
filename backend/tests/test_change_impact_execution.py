import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.ingestion.contribution_investigator import import_github_engineering_history
from backend.agents.change_room import (
    EngineeringChangeRoom,
    write_message_to_falkordb,
    read_messages_for_task,
    update_task_status_in_falkordb
)

client = TestClient(app)
WORKSPACE_ID = "ws_test_execution_suite"


@pytest.fixture(autouse=True)
def setup_test_graph():
    """Ensure clean isolated test graph in FalkorDB for each test."""
    db_client.reset_graph()
    db_client.init_schema()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield


# ----------------------------------------------------------------------------
# 1. Real Repository Can Be Imported (with labels, evidence, links)
# ----------------------------------------------------------------------------
def test_real_repository_can_be_imported():
    """Verify arbitrary public GitHub repo history is imported with labels, files, commits, PRs, and evidence nodes."""
    owner = "octocat"
    repo = "Spoon-Knife"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "default_branch": "main",
        "description": "Repositroy for Octocat Spoon-Knife testing",
        "html_url": repo_url
    }

    mock_commits = [
        {
            "sha": "c111222333444555",
            "commit": {
                "message": "fix: update index.html routing\n\nCloses #10",
                "author": {"name": "Octo Cat", "email": "octo@github.com", "date": "2026-03-01T12:00:00Z"}
            },
            "author": {"login": "octocat", "id": 1, "html_url": "https://github.com/octocat"},
            "html_url": f"{repo_url}/commit/c111222333444555"
        }
    ]

    mock_commit_detail = {
        "sha": "c111222333444555",
        "files": [{"filename": "index.html", "status": "modified", "additions": 5, "deletions": 2, "changes": 7}]
    }

    mock_pulls = [
        {
            "number": 12,
            "title": "Add Spoon Routing Feature",
            "body": "Fixes #10 and adds responsive styling",
            "state": "closed",
            "created_at": "2026-03-01T10:00:00Z",
            "closed_at": "2026-03-01T12:00:00Z",
            "merged_at": "2026-03-01T12:00:00Z",
            "html_url": f"{repo_url}/pull/12",
            "user": {"login": "octocat", "id": 1, "html_url": "https://github.com/octocat"},
            "labels": [{"name": "enhancement", "color": "a2eeef", "description": "New feature"}]
        }
    ]

    mock_issues = [
        {
            "number": 10,
            "title": "Navigation links broken on mobile",
            "body": "The spoon icon does not link to index.html",
            "state": "closed",
            "created_at": "2026-02-28T09:00:00Z",
            "closed_at": "2026-03-01T12:00:00Z",
            "html_url": f"{repo_url}/issues/10",
            "user": {"login": "mona", "id": 2, "html_url": "https://github.com/mona"},
            "labels": [{"name": "bug", "color": "d73a4a", "description": "Something isn't working"}]
        }
    ]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "50"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            if "c111222333444555" in url:
                resp.status_code = 200
                resp.json.return_value = mock_commit_detail
                return resp
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp
        if "pulls/12/files" in url:
            resp.status_code = 200
            resp.json.return_value = [{"filename": "index.html", "status": "modified", "additions": 5, "deletions": 2}]
            return resp
        if "pulls/12/reviews" in url:
            resp.status_code = 200
            resp.json.return_value = []
            return resp
        if "pulls" in url:
            resp.status_code = 200
            resp.json.return_value = mock_pulls
            return resp
        if "issues" in url:
            resp.status_code = 200
            resp.json.return_value = mock_issues
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        summary = import_github_engineering_history(
            repo_url=repo_url,
            workspace_id=WORKSPACE_ID,
            max_commits=5,
            max_pulls=5,
            max_issues=5
        )

    assert summary["status"] == "INGESTED_SUCCESS"
    assert summary["repository"]["full_name"] == f"{owner}/{repo}"
    assert summary["counts"]["commits"] == 1
    assert summary["counts"]["pull_requests"] == 1
    assert summary["counts"]["issues"] == 1
    assert summary["counts"]["labels"] >= 2
    assert summary["counts"]["resolves_relationships"] >= 1

    # Verify in FalkorDB: Labels and Evidence exist
    lbl_rows = db_client.query("MATCH (l:Label {workspace_id: $ws}) RETURN l.name", {"ws": WORKSPACE_ID})
    lbl_names = [r[0] for r in lbl_rows]
    assert "bug" in lbl_names
    assert "enhancement" in lbl_names

    ev_rows = db_client.query("MATCH (ev:Evidence {workspace_id: $ws}) RETURN ev.id, ev.kind", {"ws": WORKSPACE_ID})
    assert len(ev_rows) >= 3  # Commit, PR, Issue evidence nodes


# ----------------------------------------------------------------------------
# 2. User Question Creates a Persisted Task in FalkorDB
# ----------------------------------------------------------------------------
def test_user_question_creates_persisted_task():
    """Verify a user question or change proposal creates a persistent Task node in FalkorDB."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    question = "What files and services will this change affect?"

    result = change_room.analyze_change(question)

    # Verify task was persisted
    task_rows = db_client.query("""
    MATCH (t:Task {workspace_id: $ws})
    WHERE t.title CONTAINS $q OR t.description CONTAINS $q
    RETURN t.id, t.status, t.created_by
    """, {"ws": WORKSPACE_ID, "q": "What files"})

    assert len(task_rows) >= 1
    assert task_rows[0][0].startswith("task_change_")
    assert task_rows[0][2] in ["emp_chief_of_staff", "emp_coordinator"]


# ----------------------------------------------------------------------------
# 3. Coordinator Assigns Work
# ----------------------------------------------------------------------------
def test_coordinator_assigns_work():
    """Verify Coordinator creates the task and issues a TASK_ASSIGNED message in FalkorDB."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    result = change_room.analyze_change("Investigate Redis to Valkey migration risks")

    messages = read_messages_for_task(WORKSPACE_ID, result["timeline"][0]["message_id"].replace("msg_", "").split("_t1")[0])
    coord_msg = next((m for m in result["agent_messages"] if m["sender_id"] == "emp_chief_of_staff" and m["message_type"] == "TASK_ASSIGNED"), None)
    
    assert coord_msg is not None
    assert coord_msg["receiver_id"] == "emp_engineer"
    assert "Investigate Redis to Valkey" in coord_msg["content"]
    assert "ASSIGNED" in result["task_status_progression"]


# ----------------------------------------------------------------------------
# 4. One Agent Sends a Message Through FalkorDB
# ----------------------------------------------------------------------------
def test_one_agent_sends_message_through_falkordb():
    """Verify an agent writes a structured message to FalkorDB with graph relationships."""
    task_id = "task_test_message_hop"
    
    # Create test task
    db_client.query("""
    MERGE (t:Task {workspace_id: $ws, id: $tid})
    SET t.title = 'Test Message Hop Task', t.status = 'IN_PROGRESS'
    """, {"ws": WORKSPACE_ID, "tid": task_id})

    # Agent 1 (Code Investigator / emp_engineer) sends message
    msg_id = write_message_to_falkordb(
        workspace_id=WORKSPACE_ID,
        task_id=task_id,
        sender_id="emp_engineer",
        receiver_id="emp_eng_manager",
        message_type="INVESTIGATION_RESULT",
        content="Found critical dependency in redis_client.py touching payment retry loop.",
        evidence_ids=["ev_commit_42"],
        requested_action="Verify service ownership and team allocation",
        status="DELIVERED"
    )

    # Verify graph structure: (agent)-[:SENT]->(message)-[:TO]->(agent) and (message)-[:FOR_TASK]->(task)
    rows = db_client.query("""
    MATCH (s:Employee {id: 'emp_engineer'})-[:SENT]->(m:AgentMessage {id: $mid})-[:TO]->(r:Employee {id: 'emp_eng_manager'})
    MATCH (m)-[:FOR_TASK]->(t:Task {id: $tid})
    RETURN m.id, m.message_type, m.content
    """, {"mid": msg_id, "tid": task_id})

    assert len(rows) == 1
    assert rows[0][1] == "INVESTIGATION_RESULT"
    assert "redis_client.py" in rows[0][2]


# ----------------------------------------------------------------------------
# 5. Another Agent Reads That Message and Continues the Task
# ----------------------------------------------------------------------------
def test_another_agent_reads_message_and_continues_task():
    """Verify receiving agent reads previous messages from FalkorDB and advances bounded status."""
    task_id = "task_test_read_and_continue"

    db_client.query("""
    MERGE (t:Task {workspace_id: $ws, id: $tid})
    SET t.title = 'Sequential Handoff Test Task', t.status = 'HANDOFF_PENDING'
    """, {"ws": WORKSPACE_ID, "tid": task_id})

    # Step 1 Message
    msg1_id = write_message_to_falkordb(
        workspace_id=WORKSPACE_ID,
        task_id=task_id,
        sender_id="emp_engineer",
        receiver_id="emp_eng_manager",
        message_type="INVESTIGATION_RESULT",
        content="Code investigation complete for payment gateway.",
        status="DELIVERED"
    )

    # Step 2: Ownership Agent reads message from FalkorDB
    messages = read_messages_for_task(WORKSPACE_ID, task_id)
    assert len(messages) == 1
    assert messages[0]["content"] == "Code investigation complete for payment gateway."

    # Step 2: Ownership Agent continues work, updates status, and sends next message
    update_task_status_in_falkordb(WORKSPACE_ID, task_id, "REVIEW")
    msg2_id = write_message_to_falkordb(
        workspace_id=WORKSPACE_ID,
        task_id=task_id,
        sender_id="emp_eng_manager",
        receiver_id="emp_knowledge_mgr",
        message_type="REVIEW_REQUEST",
        content="Ownership verified for Asha Patel. Requesting architectural decision review.",
        status="DELIVERED"
    )

    # Verify both messages are in FalkorDB
    all_msgs = read_messages_for_task(WORKSPACE_ID, task_id)
    assert len(all_msgs) == 2
    assert all_msgs[1]["sender_id"] == "emp_eng_manager"

    # Verify task status is REVIEW
    t_status = db_client.query("MATCH (t:Task {id: $tid}) RETURN t.status", {"tid": task_id})[0][0]
    assert t_status == "REVIEW"


# ----------------------------------------------------------------------------
# 6. Evidence Citations Attached to Final Answer
# ----------------------------------------------------------------------------
def test_evidence_citations_attached_to_final_answer():
    """Verify final answer and response contain concrete FalkorDB evidence citations."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    result = change_room.analyze_change("Replace Redis with Valkey in the Payments service.")

    assert len(result["verified_claims"]) > 0
    # Every verified claim must reference an active entity or fact in the graph
    for claim in result["verified_claims"]:
        assert claim["status"] == "VERIFIED_IN_GRAPH"

    # Final answer is generated
    assert len(result["final_answer"]) > 20
    assert "redis_client.py" in result["final_answer"] or "Payments" in result["final_answer"]

    # GitHub issue contains FalkorDB evidence section
    issue = result["generated_github_issue"]
    assert "Evidence Citations (FalkorDB Provenance)" in issue["body"]


# ----------------------------------------------------------------------------
# 7. GitHub Follow-up Issue Can Be Created
# ----------------------------------------------------------------------------
def test_github_followup_issue_created():
    """Verify an actionable GitHub follow-up issue artifact is produced with assignees and checklist."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    result = change_room.analyze_change("Replace Redis with Valkey in the Payments service.")

    issue = result["generated_github_issue"]
    assert issue is not None
    assert issue["title"].startswith("[Change Impact]")
    assert issue["state"] == "open"
    assert len(issue["assignees"]) >= 1
    assert "impact-review" in issue["labels"]
    assert "### Actionable Implementation Checklist" in issue["body"]
    assert "- [ ]" in issue["body"]
    assert "@" in issue["body"]  # Mention of owner


# ----------------------------------------------------------------------------
# 8. Workflow Works for a Repository Other Than Seeded Example
# ----------------------------------------------------------------------------
def test_workflow_works_for_non_seeded_repository():
    """Verify the multi-agent workflow operates successfully on an arbitrary non-Payments public repository."""
    owner = "fastapi"
    repo = "fastapi"
    repo_url = f"https://github.com/{owner}/{repo}"

    mock_repo_meta = {
        "name": repo,
        "full_name": f"{owner}/{repo}",
        "default_branch": "master",
        "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
        "html_url": repo_url
    }

    mock_commits = [
        {
            "sha": "f123456789abcdef",
            "commit": {
                "message": "fix: update dependency injection resolver\n\nFixes #500",
                "author": {"name": "Sebastián Ramírez", "email": "tiangolo@example.com", "date": "2026-03-10T14:00:00Z"}
            },
            "author": {"login": "tiangolo", "id": 1326112, "html_url": "https://github.com/tiangolo"},
            "html_url": f"{repo_url}/commit/f123456789abcdef"
        }
    ]

    mock_commit_detail = {
        "sha": "f123456789abcdef",
        "files": [{"filename": "fastapi/dependencies/utils.py", "status": "modified", "additions": 12, "deletions": 4, "changes": 16}]
    }

    mock_pulls = [
        {
            "number": 501,
            "title": "Optimize dependency cache in FastAPI routing",
            "body": "This resolves #500 and prevents duplicate dependency evaluation.",
            "state": "closed",
            "created_at": "2026-03-10T12:00:00Z",
            "closed_at": "2026-03-10T14:00:00Z",
            "merged_at": "2026-03-10T14:00:00Z",
            "html_url": f"{repo_url}/pull/501",
            "user": {"login": "tiangolo", "id": 1326112, "html_url": "https://github.com/tiangolo"},
            "labels": [{"name": "performance", "color": "0e8a16", "description": "Performance improvement"}]
        }
    ]

    mock_issues = [
        {
            "number": 500,
            "title": "Async dependencies recomputed multiple times per request",
            "body": "When multiple sub-dependencies share a root dependency, it executes twice.",
            "state": "closed",
            "created_at": "2026-03-09T18:00:00Z",
            "closed_at": "2026-03-10T14:00:00Z",
            "html_url": f"{repo_url}/issues/500",
            "user": {"login": "community_dev", "id": 9999, "html_url": "https://github.com/community_dev"},
            "labels": [{"name": "bug", "color": "d73a4a", "description": "Bug fix"}]
        }
    ]

    def mock_get(url, headers=None, **kwargs):
        resp = MagicMock()
        resp.headers = {"content-type": "application/vnd.github.v3+json", "x-ratelimit-remaining": "50"}
        if url == f"https://api.github.com/repos/{owner}/{repo}":
            resp.status_code = 200
            resp.json.return_value = mock_repo_meta
            return resp
        if "commits" in url:
            if "f123456789abcdef" in url:
                resp.status_code = 200
                resp.json.return_value = mock_commit_detail
                return resp
            resp.status_code = 200
            resp.json.return_value = mock_commits
            return resp
        if "pulls/501/files" in url:
            resp.status_code = 200
            resp.json.return_value = [{"filename": "fastapi/dependencies/utils.py", "status": "modified", "additions": 12, "deletions": 4}]
            return resp
        if "pulls/501/reviews" in url:
            resp.status_code = 200
            resp.json.return_value = []
            return resp
        if "pulls" in url:
            resp.status_code = 200
            resp.json.return_value = mock_pulls
            return resp
        if "issues" in url:
            resp.status_code = 200
            resp.json.return_value = mock_issues
            return resp
        resp.status_code = 404
        return resp

    with patch("httpx.Client.get", side_effect=mock_get):
        import_github_engineering_history(
            repo_url=repo_url,
            workspace_id=WORKSPACE_ID,
            max_commits=5,
            max_pulls=5,
            max_issues=5
        )

    # Ask change question targeted at FastAPI repo
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    res = change_room.analyze_change("What files and PRs will changing dependency resolver in fastapi affect?")

    assert res["task_status_progression"][-1] in ["COMPLETED", "APPROVED"]
    assert res["generated_github_issue"]["repository"] == "fastapi/fastapi"
    assert len(res["timeline"]) == 6
    assert len(res["agent_messages"]) == 6


# ----------------------------------------------------------------------------
# 9. Retrying an Agent Does Not Create Duplicate Messages or Duplicate Tasks
# ----------------------------------------------------------------------------
def test_retrying_agent_does_not_create_duplicate_messages_or_tasks():
    """Verify that retrying or executing the workflow repeatedly is idempotent."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    proposal = "Replace Redis with Valkey in the Payments service."

    # Run Turn 1
    res1 = change_room.analyze_change(proposal)
    task_count_1 = db_client.query("MATCH (t:Task {workspace_id: $ws}) RETURN count(t)", {"ws": WORKSPACE_ID})[0][0]
    msg_count_1 = db_client.query("MATCH (m:AgentMessage {workspace_id: $ws}) RETURN count(m)", {"ws": WORKSPACE_ID})[0][0]

    # Re-run / Retry same proposal (simulating a retry of the agent turn)
    res2 = change_room.analyze_change(proposal)
    task_count_2 = db_client.query("MATCH (t:Task {workspace_id: $ws}) RETURN count(t)", {"ws": WORKSPACE_ID})[0][0]
    msg_count_2 = db_client.query("MATCH (m:AgentMessage {workspace_id: $ws}) RETURN count(m)", {"ws": WORKSPACE_ID})[0][0]

    # Deterministic IDs ensure count does not grow uncontrollably
    assert task_count_2 == task_count_1
    assert msg_count_2 == msg_count_1


# ----------------------------------------------------------------------------
# 10. Six Core Question Types
# ----------------------------------------------------------------------------
def test_six_user_questions():
    """Verify the 6 core questions from the prompt are handled with appropriate question intent."""
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)

    questions = [
        ("What contribution did person Asha Patel make?", "PERSON_CONTRIBUTIONS"),
        ("Which issue did PR #42 resolve?", "RESOLVED_ISSUES"),
        ("What files and services will this change affect?", "AFFECTED_AREAS"),
        ("Who owns the affected area?", "AREA_OWNERSHIP"),
        ("Which previous decisions are related?", "RELATED_DECISIONS"),
        ("What risks or dependencies exist?", "RISKS_DEPENDENCIES"),
    ]

    for q_text, expected_intent in questions:
        res = change_room.analyze_change(q_text)
        assert res["question_intent"] == expected_intent, f"Failed on query: '{q_text}'"
        assert res["final_answer"] is not None
        assert len(res["final_answer"]) > 10
        assert res["task_status_progression"][-1] in ["COMPLETED", "APPROVED"]
