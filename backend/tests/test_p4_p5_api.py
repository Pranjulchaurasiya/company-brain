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
    assert "Generality check successfully executed" in data["message"]
    assert len(data["result"]["agent_turns"]) == 4

if __name__ == "__main__":
    pytest.main(["-s", __file__])
