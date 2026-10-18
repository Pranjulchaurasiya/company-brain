import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures

client = TestClient(app)
WORKSPACE_ID = "ws_test_api"

@pytest.fixture(autouse=True)
def setup_api():
    db_client.reset_graph()
    import_all_fixtures(workspace_id=WORKSPACE_ID)
    yield

def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["connected"] is True

def test_api_workspace():
    res = client.get(f"/api/workspace?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    data = res.json()
    assert data["node_count"] > 10
    assert len(data["employees"]) >= 4
    
    # Assert employee ID uniqueness (regression test for duplicate employee issue)
    emp_ids = [e["id"] for e in data["employees"]]
    assert len(emp_ids) == len(set(emp_ids)), f"Duplicate employee IDs found: {emp_ids}"
    
    # Verify Sophia Wu exists and appears exactly once
    sophia_matches = [e for e in data["employees"] if "Sophia" in e.get("name", "")]
    assert len(sophia_matches) == 1, f"Expected exactly 1 Sophia Wu, found {len(sophia_matches)}"
    assert sophia_matches[0]["skills"], "Sophia Wu should have skills intact"

def test_api_graph_stats():
    res = client.get(f"/api/graph/stats?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    data = res.json()
    assert "node_count" in data
    assert "edge_count" in data
    assert data["node_count"] > 0
    assert data["edge_count"] > 0

    # Cross-verify with /api/workspace
    ws_res = client.get(f"/api/workspace?workspace_id={WORKSPACE_ID}")
    assert ws_res.status_code == 200
    ws_data = ws_res.json()
    assert data["node_count"] == ws_data["node_count"]
    assert data["edge_count"] == ws_data["edge_count"]

def test_api_graph():
    res = client.get(f"/api/graph?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0

def test_api_queries():
    # Owner
    res = client.get(f"/api/queries/owner?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    assert res.json()["current_owner"]["name"] == "Asha Patel"

    # Risks
    res = client.get(f"/api/queries/risks?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    risks = res.json()
    assert any(r["ticket_key"] == "PAY-104" for r in risks)

    # Decisions
    res = client.get(f"/api/queries/decisions?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    decs = res.json()
    assert any(d["decision_id"] == "dec_adr_0042" for d in decs)

    # Multi-hop
    res = client.get(f"/api/queries/multi-hop?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    path_str = res.json().get("relationship_path", "")
    assert "USES_SERVICE" in path_str
    assert "Asha Patel" in path_str

def test_api_workflow_and_deliverable():
    # Run workflow
    res = client.post("/api/workflow/run", json={
        "goal": "Prepare Payments API for the next release.",
        "project_id": "proj_payments_v2",
        "workspace_id": WORKSPACE_ID
    })
    assert res.status_code == 200
    data = res.json()
    assert len(data["agent_turns"]) == 4
    assert data["deliverable"] is not None
    assert "Release-Readiness" in data["deliverable"]["title"]

    # Fetch deliverable via API
    res_deliv = client.get(f"/api/deliverable/latest?workspace_id={WORKSPACE_ID}")
    assert res_deliv.status_code == 200
    assert res_deliv.json()["status"] == "COMPLETED"

    # Verify memory recall has complete provenance for the workflow-created memory
    res_mem = client.get(f"/api/memory/recall?workspace_id={WORKSPACE_ID}")
    assert res_mem.status_code == 200
    mems = res_mem.json()
    wf_mem = next((m for m in mems if m["type"] == "WORKFLOW_FINDING"), None)
    assert wf_mem is not None
    assert wf_mem["originating_task"] is not None
    assert wf_mem["originating_task"]["id"] is not None
    assert wf_mem["evidence"] is not None
    assert wf_mem["evidence"]["id"] is not None
    assert wf_mem["evidence"]["excerpt"]
    assert wf_mem["source"] is not None
    assert wf_mem["source"]["title"] is not None
    assert len(wf_mem.get("evidence_citations", [])) >= 1

def test_api_supersession_and_memory():
    # Trigger supersession
    res = client.post("/api/freshness/supersede", json={
        "workspace_id": WORKSPACE_ID,
        "project_id": "proj_payments_v2",
        "new_owner_id": "emp_eng_manager"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "SUPERSEDED_SUCCESS"

    # Verify owner changed
    res_owner = client.get(f"/api/queries/owner?workspace_id={WORKSPACE_ID}")
    assert res_owner.json()["current_owner"]["name"] == "Marcus Chen"

    # Recall memory in fresh session
    res_mem = client.get(f"/api/memory/recall?workspace_id={WORKSPACE_ID}")
    assert res_mem.status_code == 200
    assert len(res_mem.json()) >= 1

def test_api_generality_workflow():
    res = client.post(f"/api/generality/run?workspace_id={WORKSPACE_ID}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["result"]["agent_turns"]) >= 3
    # Verify dynamic routing selected the infrastructure specialist (emp_prior_dev) instead of fixed payments engineer
    assert any(t["employee_id"] == "emp_prior_dev" for t in data["result"]["agent_turns"])

if __name__ == "__main__":
    pytest.main(["-s", __file__])
