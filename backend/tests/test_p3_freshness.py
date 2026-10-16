import pytest
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.db.queries import get_current_owner, get_ownership_history
from backend.ingestion.freshness import supersede_ownership_fact, recall_cross_session_memory
from backend.agents.coordinator import Coordinator

WORKSPACE_ID = "ws_test_p3_company"

@pytest.fixture(autouse=True)
def setup_db():
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield

def test_fact_supersession_and_history():
    # 1. Before update: Current owner is Asha Patel
    initial_owner = get_current_owner(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert initial_owner["employee_id"] == "emp_engineer"
    assert initial_owner["name"] == "Asha Patel"

    # 2. Trigger live supersession: ownership transferred to Marcus Chen
    announcement = "Effective immediately, Marcus Chen (@marcus) assumes operational lead of Payments API v2 during the release cutoff."
    res = supersede_ownership_fact(
        workspace_id=WORKSPACE_ID,
        project_id="proj_payments_v2",
        new_owner_id="emp_eng_manager",
        announcement_text=announcement
    )

    assert res["status"] == "SUPERSEDED_SUCCESS"
    assert res["new_owner_id"] == "emp_eng_manager"

    # 3. Query current owner again: MUST return Marcus Chen
    updated_owner = get_current_owner(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert updated_owner is not None
    assert updated_owner["employee_id"] == "emp_eng_manager"
    assert updated_owner["name"] == "Marcus Chen"
    assert updated_owner["status"] == "ACTIVE"

    # 4. Check full audit history: Old facts exist as SUPERSEDED but are never active
    history = get_ownership_history(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert len(history) == 3
    # Top is Marcus (ACTIVE)
    assert history[0]["status"] == "ACTIVE"
    assert history[0]["employee_name"] == "Marcus Chen"
    # Second is Asha (SUPERSEDED)
    assert history[1]["status"] == "SUPERSEDED"
    assert history[1]["employee_name"] == "Asha Patel"
    # Third is David (SUPERSEDED)
    assert history[2]["status"] == "SUPERSEDED"
    assert history[2]["employee_name"] == "David Kim"

    print("\n[PASS] Fact supersession verified: Outdated facts remain historically auditable but are never presented as current.")

def test_cross_session_memory_recall():
    # 1. First session: Coordinator runs goal workflow and persists findings
    coordinator = Coordinator(workspace_id=WORKSPACE_ID, max_turns=4)
    res = coordinator.run_goal_workflow("Prepare Payments API release readiness")
    assert res["deliverable"] is not None

    # 2. Start a fresh session simulation (new invocation, zero chat transcript, pure graph query)
    memories = recall_cross_session_memory(workspace_id=WORKSPACE_ID, search_query="Payments")
    assert len(memories) >= 1

    workflow_memory = next((m for m in memories if m["type"] == "WORKFLOW_FINDING"), None)
    assert workflow_memory is not None
    assert "PAY-104" in workflow_memory["content"]
    assert workflow_memory["project"]["id"] == "proj_payments_v2"
    assert workflow_memory["originating_task"] is not None

    print("\n[PASS] Cross-session memory recall verified: Follow-up question retrieves prior findings and tasks without conversational history.")

if __name__ == "__main__":
    pytest.main(["-s", __file__])
