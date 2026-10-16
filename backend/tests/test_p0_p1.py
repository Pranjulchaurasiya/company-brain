import pytest
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.db.queries import (
    get_current_owner,
    get_ownership_history,
    get_unresolved_risks,
    get_decisions_for_project,
    get_expertise_by_skill,
    get_multi_hop_path
)

WORKSPACE_ID = "ws_test_company"

@pytest.fixture(autouse=True)
def setup_db():
    # Reset before test
    db_client.reset_graph()
    yield

def test_idempotent_ingestion():
    # Run 1
    stats1 = import_all_fixtures(workspace_id=WORKSPACE_ID)
    g = db_client.get_graph()
    count_nodes_1 = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": WORKSPACE_ID}).result_set[0][0]
    count_edges_1 = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": WORKSPACE_ID}).result_set[0][0]

    # Run 2 (Should not duplicate anything!)
    stats2 = import_all_fixtures(workspace_id=WORKSPACE_ID)
    count_nodes_2 = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": WORKSPACE_ID}).result_set[0][0]
    count_edges_2 = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": WORKSPACE_ID}).result_set[0][0]

    assert count_nodes_1 == count_nodes_2, f"Nodes duplicated! Before: {count_nodes_1}, After: {count_nodes_2}"
    assert count_edges_1 == count_edges_2, f"Edges duplicated! Before: {count_edges_1}, After: {count_edges_2}"
    print(f"\n[PASS] Idempotency verified: exactly {count_nodes_1} nodes and {count_edges_1} edges preserved across re-runs.")

def test_p1_queries():
    import_all_fixtures(workspace_id=WORKSPACE_ID)

    # 1. Current owner query
    owner = get_current_owner(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert owner is not None
    assert owner["employee_id"] == "emp_engineer"
    assert owner["name"] == "Asha Patel"
    assert owner["status"] == "ACTIVE"
    assert owner["evidence"] is not None
    assert "Asha Patel (@asha) is taking over" in owner["evidence"]["excerpt"]
    assert owner["source"]["type"] == "CHAT"

    # 2. Ownership history query (shows both superseded and active)
    history = get_ownership_history(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert len(history) == 2
    # Newest is Asha (ACTIVE), prior is David (SUPERSEDED)
    assert history[0]["status"] == "ACTIVE"
    assert history[0]["employee_name"] == "Asha Patel"
    assert history[1]["status"] == "SUPERSEDED"
    assert history[1]["employee_name"] == "David Kim"
    assert history[0]["supersedes_fact_id"] == history[1]["fact_id"]

    # 3. Unresolved risks query (Ticket PAY-104)
    risks = get_unresolved_risks(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert len(risks) >= 1
    pay104 = next(r for r in risks if r["ticket_key"] == "PAY-104")
    assert pay104["status"] == "BLOCKED"
    assert "race condition" in pay104["description"]
    assert pay104["service_name"] == "Payments Settlement Service"

    # 4. Decisions query (ADR-0042)
    decisions = get_decisions_for_project(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert len(decisions) >= 1
    adr0042 = next(d for d in decisions if d["decision_id"] == "dec_adr_0042")
    assert "ADR-0042" in adr0042["outcome"]
    assert adr0042["status"] == "ACCEPTED"
    assert adr0042["decided_by"] == "Asha Patel"

    # 5. Multi-hop path query
    path = get_multi_hop_path(workspace_id=WORKSPACE_ID, project_id="proj_payments_v2")
    assert path["project"] == "Payments API v2"
    assert path["service"] == "Payments Settlement Service"
    assert "PAY-104" in path["unresolved_risk_ticket"]
    assert path["current_owner"] == "Asha Patel"

    # 6. Expertise query
    experts = get_expertise_by_skill(workspace_id=WORKSPACE_ID, skill_keyword="Idempotency")
    assert len(experts) >= 1
    assert experts[0]["name"] == "Asha Patel"

    print("\n[PASS] All P1 queries verified against FalkorDB graph.")

if __name__ == "__main__":
    pytest.main(["-s", __file__])
