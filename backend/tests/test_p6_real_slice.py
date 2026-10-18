import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.ingestion.external_importer import store_imported_documents, parse_github_repo_url
from backend.agents.retrieval import search_graph_evidence
from backend.agents.coordinator import Coordinator

client = TestClient(app)
WORKSPACE_ID = "ws_test_p6_slice"

@pytest.fixture(autouse=True)
def setup_slice():
    # Setup isolated test database for P6 vertical slice
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield

def test_github_url_parser():
    assert parse_github_repo_url("https://github.com/octocat/Hello-World") == ("octocat", "Hello-World")
    assert parse_github_repo_url("github.com/owner/repo.git") == ("owner", "repo")
    assert parse_github_repo_url("acme/platform-core") == ("acme", "platform-core")
    assert parse_github_repo_url("invalid-url") is None

def test_import_external_documents_and_graph_query():
    # 1. Import a real non-Payments document into the test graph
    rfc_doc = {
        "title": "RFC-0089: Zero-Trust Telemetry Architecture",
        "path": "docs/architecture/rfc-0089-telemetry.md",
        "content": (
            "# RFC-0089: Zero-Trust Telemetry Architecture\n\n"
            "This RFC defines the telemetry pipeline across our cloud infrastructure.\n\n"
            "All distributed traces must emit W3C tracecontext headers and route through "
            "the OpenTelemetry Collector daemon running on port 4317.\n\n"
            "Security constraints mandate TLS 1.3 mutual authentication for all telemetry exporters, "
            "with certificates rotated every 30 days by Vault.\n\n"
            "Accountable architecture lead is David Kim from Infrastructure Engineering."
        )
    }

    import_result = store_imported_documents(
        documents=[rfc_doc],
        project_name="Telemetry Infrastructure",
        project_id="proj_telemetry_infra",
        source_type="IMPORTED_RFC",
        workspace_id=WORKSPACE_ID
    )

    assert import_result["status"] == "INGESTED_SUCCESS"
    assert import_result["sources_created"] == 1
    assert import_result["evidence_created"] >= 3

    # 2. Query FalkorDB directly to verify Source and Evidence records with locators
    g = db_client.get_graph()
    src_rows = g.query("""
    MATCH (p:Project {workspace_id: $ws, id: 'proj_telemetry_infra'})-[:HAS_SOURCE]->(s:Source)
    RETURN s.id, s.title, s.source_type, s.is_synthetic
    """, {"ws": WORKSPACE_ID}).result_set

    assert len(src_rows) == 1
    assert src_rows[0][1] == "RFC-0089: Zero-Trust Telemetry Architecture"
    assert src_rows[0][3] is False # Verified as non-synthetic imported context

    # 3. Check Evidence locators
    ev_rows = g.query("""
    MATCH (ev:Evidence {workspace_id: $ws})-[:FROM_SOURCE]->(s:Source {id: $sid})
    RETURN ev.id, ev.excerpt, ev.locator
    """, {"ws": WORKSPACE_ID, "sid": src_rows[0][0]}).result_set

    assert len(ev_rows) >= 3
    for ev in ev_rows:
        assert "#L" in ev[2], f"Expected line locator like #L1-L5, got {ev[2]}"
        assert len(ev[1]) > 10

def test_unseen_non_payments_question_grounded_answer():
    # Ingest non-Payments architecture doc
    doc = {
        "title": "Observability Exporter Spec",
        "path": "specs/observability.md",
        "content": (
            "The OpenTelemetry Collector daemon runs on port 4317.\n"
            "All spans must be batch-exported with 5-second flushes.\n"
            "Retention for raw spans is 14 days in ClickHouse storage."
        )
    }
    store_imported_documents(
        documents=[doc],
        project_name="Observability",
        project_id="proj_observability",
        source_type="SPEC",
        workspace_id=WORKSPACE_ID
    )

    # Ask unseen question
    res = search_graph_evidence(
        workspace_id=WORKSPACE_ID,
        query_text="What port does the OpenTelemetry Collector daemon run on?"
    )

    assert res["has_evidence"] is True
    assert res["verdict"] == "DOCUMENTED"
    assert "4317" in res["answer"]
    assert len(res["citations"]) >= 1
    assert any("4317" in c["excerpt"] for c in res["citations"])
    assert res["citations"][0]["locator"].startswith("specs/observability.md#L")

def test_absent_question_honest_abstention():
    # Ask about a topic completely missing from the graph
    res = search_graph_evidence(
        workspace_id=WORKSPACE_ID,
        query_text="What is the quantum encryption protocol and laser satellite uplink frequency?"
    )

    assert res["has_evidence"] is False
    assert res["verdict"] == "NOT_DOCUMENTED"
    assert "Not documented" in res["answer"]
    assert len(res["checked_sources"]) >= 3
    # Critical invariant: must NOT return canned Payments answers
    assert "PAY-104" not in res["answer"]
    assert "Asha Patel" not in res["answer"]
    assert len(res["citations"]) == 0

def test_dynamic_request_driven_employee_routing():
    coordinator = Coordinator(workspace_id=WORKSPACE_ID)

    # 1. Payments release readiness -> routes to full 4-turn Payments team
    seq_payments = coordinator.select_employee_sequence("Prepare Payments API release readiness", "proj_payments_v2")
    emp_ids_payments = [s[0] for s in seq_payments]
    assert emp_ids_payments == ["emp_chief_of_staff", "emp_eng_manager", "emp_engineer", "emp_knowledge_mgr"]

    # 2. Infrastructure & Kafka goal -> dynamically selects David Kim (emp_prior_dev), Senior Infrastructure Engineer
    seq_infra = coordinator.select_employee_sequence("Evaluate Kafka streaming cluster and database migration readiness", "proj_core_infra")
    emp_ids_infra = [s[0] for s in seq_infra]
    assert "emp_prior_dev" in emp_ids_infra
    assert "emp_engineer" not in emp_ids_infra # Replaced by infrastructure specialist

    # 3. Security & Operational Incident -> routes to Sophia Wu (emp_knowledge_mgr / Operations)
    seq_sec = coordinator.select_employee_sequence("Audit security incident response and operational monitoring policies", "proj_security")
    emp_ids_sec = [s[0] for s in seq_sec]
    assert "emp_knowledge_mgr" in emp_ids_sec

    # Run the infra workflow and verify execution
    res = coordinator.run_goal_workflow("Evaluate Kafka streaming cluster and database migration readiness", "proj_core_infra")
    assert len(res["agent_turns"]) == 3
    assert any(t["employee_id"] == "emp_prior_dev" for t in res["agent_turns"])

def test_persisted_task_deliverable_goal_linking_and_badge():
    coordinator = Coordinator(workspace_id=WORKSPACE_ID)
    goal_text = "Prepare Payments API for the next release"
    result = coordinator.run_goal_workflow(goal_text, "proj_payments_v2")

    deliverable = result["deliverable"]
    assert deliverable is not None
    # Verify badge is "Completed with conditions" because release is blocked by PAY-104
    assert result["deliverable_badge"] == "Completed with conditions"
    assert deliverable["badge_status"] == "Completed with conditions"
    assert "BLOCK" in deliverable["readiness_verdict"]

    # Verify FalkorDB persistence of Goal and links
    g = db_client.get_graph()
    goal_rows = g.query("MATCH (g:Goal {workspace_id: $ws}) RETURN g.id, g.title", {"ws": WORKSPACE_ID}).result_set
    assert len(goal_rows) >= 1

    # Verify Tasks link to Goal
    task_goal_links = g.query("MATCH (g:Goal {workspace_id: $ws})-[:HAS_TASK]->(t:Task) RETURN count(t)", {"ws": WORKSPACE_ID}).result_set
    assert task_goal_links[0][0] >= 3

    # Verify real in-app remediation task was created
    remediation_task = g.query("MATCH (t:Task {workspace_id: $ws}) WHERE t.title CONTAINS 'PAY-104' OR t.title CONTAINS 'remediation' RETURN t.id, t.status", {"ws": WORKSPACE_ID}).result_set
    assert len(remediation_task) >= 1

    # Verify external actions require human approval
    for turn in result["agent_turns"]:
        for action in turn["actions"]:
            if action.get("tool_id") in ("send_slack_message", "comment_github_pr"):
                assert action["arguments"]["requires_human_approval"] is True
                assert action["arguments"]["external_write_executed"] is False

def test_api_real_slice_endpoints():
    # 1. Test Ingest Document via API
    res_ingest = client.post("/api/ingest/document", json={
        "title": "Incident Playbook 101",
        "content": "For P0 incidents, notify the incident commander on Slack channel #incident-bridge within 5 minutes.",
        "path": "playbooks/p0.md",
        "project_name": "Operations Playbooks",
        "workspace_id": WORKSPACE_ID
    })
    assert res_ingest.status_code == 200
    data_ingest = res_ingest.json()
    assert data_ingest["status"] == "INGESTED_SUCCESS"
    assert data_ingest["evidence_created"] >= 1

    # 2. Test Ask supported question via API
    res_ask = client.post("/api/ask", json={
        "query": "What is the notification timeframe for P0 incidents?",
        "workspace_id": WORKSPACE_ID
    })
    assert res_ask.status_code == 200
    data_ask = res_ask.json()
    assert data_ask["has_evidence"] is True
    assert data_ask["verdict"] == "DOCUMENTED"
    assert "5 minutes" in data_ask["answer"]
    assert len(data_ask["citations"]) >= 1

    # 3. Test Ask absent question via API
    res_absent = client.post("/api/ask", json={
        "query": "What is the secret passphrase for interstellar teleportation?",
        "workspace_id": WORKSPACE_ID
    })
    assert res_absent.status_code == 200
    data_absent = res_absent.json()
    assert data_absent["has_evidence"] is False
    assert data_absent["verdict"] == "NOT_DOCUMENTED"
    assert "Not documented" in data_absent["answer"]

if __name__ == "__main__":
    pytest.main(["-s", __file__])
