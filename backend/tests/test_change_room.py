import pytest
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.agents.change_room import EngineeringChangeRoom, read_messages_for_task
from backend.ingestion.freshness import toggle_ownership_fact

WORKSPACE_ID = "ws_test_change_room"

@pytest.fixture(autouse=True)
def setup_db():
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield

def test_change_room_redis_to_valkey_workflow():
    """
    Test core Engineering Change Room question:
    'If we make this change, what will be affected, who owns it, who knows it,
    which decision supports it, and what work must happen next?'
    """
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    proposed_change = "Replace Redis with Valkey in the Payments service."
    
    result = change_room.analyze_change(proposed_change)

    # 1. Output Structure
    assert result["proposed_change"] == proposed_change
    assert result["change_id"].startswith("change_")

    # 2. Affected Service & File
    assert len(result["affected_services"]) == 1
    assert result["affected_services"][0]["name"] == "Payments Settlement Service"
    assert len(result["affected_files"]) == 1
    assert result["affected_files"][0]["filename"] == "redis_client.py"

    # 3. Related PR and Issue
    assert len(result["related_pull_requests"]) == 1
    assert result["related_pull_requests"][0]["number"] == 42
    assert len(result["related_issues"]) == 1
    assert result["related_issues"][0]["number"] == 31

    # 4. Current Owner
    assert result["current_owner"] is not None
    assert result["current_owner"]["name"] == "Asha Patel"

    # 5. Architecture Decision (ADR-0042)
    assert len(result["architecture_decisions"]) == 1
    assert result["architecture_decisions"][0]["id"] == "dec_adr_0042"

    # 6. Canonical Sequential Impact Path
    expected_path = "Proposed Change: 'Replace Redis with Valkey in the Payments service.' → Payments Settlement Service → redis_client.py → PR #42 → Issue #31 → Asha Patel → ADR-0042 → Review Valkey migration impact on payment retry worker"
    assert result["impact_path_string"] == expected_path

    # 7. Follow-up Work Output Created in FalkorDB
    followup = result["followup_task"]
    assert followup is not None
    assert "Review Valkey migration impact on payment retry worker" in followup["title"]
    assert followup["assigned_to_name"] == "Asha Patel"
    assert followup["status"] == "READY_FOR_ASSIGNMENT"

    # Verify relationships in FalkorDB
    g = db_client.get_graph()
    task_id = followup["id"]

    # Verify Task linked to Service
    svc_links = g.query("""
    MATCH (t:Task {workspace_id: $ws, id: $tid})-[:AFFECTS_SERVICE]->(s:Service)
    RETURN s.name
    """, {"ws": WORKSPACE_ID, "tid": task_id}).result_set
    assert len(svc_links) == 1
    assert svc_links[0][0] == "Payments Settlement Service"

    # Verify Task assigned to Owner
    assignee_links = g.query("""
    MATCH (t:Task {workspace_id: $ws, id: $tid})-[:ASSIGNED_TO]->(e:Employee)
    RETURN e.name
    """, {"ws": WORKSPACE_ID, "tid": task_id}).result_set
    assert len(assignee_links) == 1
    assert assignee_links[0][0] == "Asha Patel"

    # Verify Deliverable was persisted
    deliv_rows = g.query("""
    MATCH (d:Deliverable {workspace_id: $ws, deliverable_type: 'CHANGE_IMPACT_REPORT'})
    RETURN d.title, d.status
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(deliv_rows) >= 1
    assert deliv_rows[0][1] == "COMPLETED"

def test_agents_communicate_via_falkordb_message_bus():
    """
    Verify agents communicate through FalkorDB messages and not through hidden direct function calls:
    (Employee)-[:SENT]->(AgentMessage)-[:TO]->(Employee)
    (AgentMessage)-[:FOR_TASK]->(Task)
    (AgentMessage)-[:SUPPORTED_BY]->(Evidence)
    """
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    proposed_change = "Replace Redis with Valkey in the Payments service."
    result = change_room.analyze_change(proposed_change)

    messages = result["agent_messages"]
    assert len(messages) >= 4, f"Expected at least 4 durable messages, got {len(messages)}"

    # Check message types sequence: TASK_ASSIGNED -> REVIEW_REQUEST -> REVIEW_RESULT -> TASK_COMPLETED
    msg_types = [m["message_type"] for m in messages]
    assert "TASK_ASSIGNED" in msg_types
    assert "REVIEW_REQUEST" in msg_types
    assert "REVIEW_RESULT" in msg_types
    assert "TASK_COMPLETED" in msg_types

    # Verify relationships in FalkorDB
    g = db_client.get_graph()

    # Verify SENT and TO edges between Employee and AgentMessage
    sent_edges = g.query("""
    MATCH (e:Employee {workspace_id: $ws})-[:SENT]->(m:AgentMessage)-[:TO]->(r:Employee)
    RETURN e.name, m.message_type, r.name
    """, {"ws": WORKSPACE_ID}).result_set
    assert len(sent_edges) >= 4

    # Verify AgentMessages are linked to Task
    task_edges = g.query("""
    MATCH (m:AgentMessage {workspace_id: $ws})-[:FOR_TASK]->(t:Task)
    RETURN count(m)
    """, {"ws": WORKSPACE_ID}).result_set
    assert task_edges[0][0] >= 4

    # Verify AgentMessages are linked to Evidence
    ev_edges = g.query("""
    MATCH (m:AgentMessage {workspace_id: $ws})-[:SUPPORTED_BY]->(ev:Evidence)
    RETURN count(m)
    """, {"ws": WORKSPACE_ID}).result_set
    assert ev_edges[0][0] >= 1

def test_honest_abstention_when_not_in_graph():
    """
    If the graph cannot prove something, verify it shows:
    'Not documented in the company graph.'
    """
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    proposed_change = "Migrate from Cassandra to DynamoDB in Billing Service."
    
    result = change_room.analyze_change(proposed_change)

    # Since Cassandra and Billing Service do not exist in graph:
    assert len(result["unproven_items"]) > 0
    path_labels = [node["label"] for node in result["impact_path"]]
    assert "Not documented in the company graph." in path_labels
    assert "Not documented in the company graph." in result["impact_path_string"]

def test_freshness_owner_toggle_changes_assignee():
    """
    Demo Button: 'Change owner'
    Change the owner from Asha to Marcus, re-run the same analysis, and show that
    the recommended assignee changes dynamically.
    Proves graph state is operational, not decoration.
    """
    change_room = EngineeringChangeRoom(workspace_id=WORKSPACE_ID)
    proposed_change = "Replace Redis with Valkey in the Payments service."

    # Run 1: Active owner is Asha Patel
    res1 = change_room.analyze_change(proposed_change)
    assert res1["current_owner"]["name"] == "Asha Patel"
    assert res1["followup_task"]["assigned_to_name"] == "Asha Patel"
    assert "→ Asha Patel →" in res1["impact_path_string"]

    # DEMO ACTION: Change owner (Asha -> Marcus)
    toggle_res = toggle_ownership_fact(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert toggle_res["status"] == "SUPERSEDED_SUCCESS"
    assert toggle_res["new_owner_id"] == "emp_eng_manager"
    assert toggle_res["updated_owner"]["name"] == "Marcus Chen"

    # Run 2: Re-run analysis; recommended owner and assignee must now be Marcus Chen!
    res2 = change_room.analyze_change(proposed_change)
    assert res2["current_owner"]["name"] == "Marcus Chen"
    assert res2["followup_task"]["assigned_to_name"] == "Marcus Chen"
    assert "→ Marcus Chen →" in res2["impact_path_string"]

    # DEMO ACTION: Toggle back to Asha Patel
    toggle_back = toggle_ownership_fact(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert toggle_back["updated_owner"]["name"] == "Asha Patel"

    # Run 3: Returns to Asha Patel
    res3 = change_room.analyze_change(proposed_change)
    assert res3["current_owner"]["name"] == "Asha Patel"
    assert res3["followup_task"]["assigned_to_name"] == "Asha Patel"
    assert "→ Asha Patel →" in res3["impact_path_string"]

