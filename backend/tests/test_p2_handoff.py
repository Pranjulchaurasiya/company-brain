import pytest
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.agents.coordinator import Coordinator

WORKSPACE_ID = "ws_test_p2_company"

@pytest.fixture(autouse=True)
def setup_db():
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield

def test_employee_handoff_and_persistence():
    coordinator = Coordinator(workspace_id=WORKSPACE_ID, max_turns=5)
    goal = "Prepare Payments API for the next release. Find the current owner, explain the unresolved risk and the decision behind it, then coordinate the next investigation."
    
    result = coordinator.run_goal_workflow(goal_text=goal, project_id="proj_payments_v2")

    # 1. Verify workflow output
    assert result["session_id"].startswith("sess_")
    assert "Asha Patel" in result["readiness_summary"]
    assert "PAY-104" in result["readiness_summary"]
    assert len(result["handoffs"]) >= 2
    assert len(result["agent_turns"]) == 4

    # 2. Verify Deliverable was produced and saved
    deliverable = result["deliverable"]
    assert deliverable is not None
    assert "Release-Readiness Assessment" in deliverable["title"]
    assert deliverable["author_name"] == "Asha Patel"
    assert "BLOCKED_PENDING_MUTEX_PR" in deliverable["readiness_verdict"]

    # 3. Verify Citations are cross-source
    citations = result["citations"]
    assert len(citations) >= 3
    ev_ids = [c["evidence_id"] for c in citations]
    assert "ev_brief_scope" in ev_ids # Document citation
    assert "ev_pay_104_risk" in ev_ids # Ticket citation
    assert "ev_chat_ownership_transfer" in ev_ids # Chat citation

    # 4. Verify FalkorDB persistence of messages, tasks, deliverables, and memories
    g = db_client.get_graph()
    
    # Check AgentMessages stored
    msg_rows = g.query("MATCH (m:AgentMessage {workspace_id: $ws}) RETURN count(m)", {"ws": WORKSPACE_ID}).result_set
    assert msg_rows[0][0] >= 4, f"Expected at least 4 messages persisted, got {msg_rows[0][0]}"

    # Check Task status is DONE
    task_rows = g.query("MATCH (t:Task {workspace_id: $ws, status: 'DONE'}) RETURN count(t)", {"ws": WORKSPACE_ID}).result_set
    assert task_rows[0][0] >= 3, f"Expected at least 3 completed tasks, got {task_rows[0][0]}"

    # Check Deliverable node persisted
    deliv_rows = g.query("MATCH (d:Deliverable {workspace_id: $ws, id: 'deliv_payments_readiness_plan'}) RETURN d.title, d.status", {"ws": WORKSPACE_ID}).result_set
    assert len(deliv_rows) == 1
    assert deliv_rows[0][1] == "COMPLETED"

    # Check Memory node persisted
    mem_rows = g.query("MATCH (m:Memory {workspace_id: $ws}) RETURN count(m)", {"ws": WORKSPACE_ID}).result_set
    assert mem_rows[0][0] >= 1, "Expected Memory node persisted in FalkorDB"

    print("\n[PASS] Employee handoff, multi-agent collaboration, and FalkorDB persistence verified successfully!")

if __name__ == "__main__":
    pytest.main(["-s", __file__])
