import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.config import DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client
from backend.ingestion.importer import import_all_fixtures
from backend.db.queries import (
    get_current_owner,
    get_ownership_history,
    get_unresolved_risks,
    get_decisions_for_project,
    get_expertise_by_skill,
    get_multi_hop_path,
    get_all_employees,
    get_graph_snapshot
)
from backend.agents.coordinator import Coordinator
from backend.ingestion.freshness import (
    supersede_ownership_fact,
    recall_cross_session_memory,
    toggle_ownership_fact
)
from backend.ingestion.external_importer import import_github_repo, store_imported_documents
from backend.ingestion.contribution_investigator import (
    import_github_engineering_history,
    get_person_contributions
)
from backend.agents.retrieval import search_graph_evidence
from backend.agents.change_room import EngineeringChangeRoom, read_messages_for_task
from backend.models.schema import ChangeProposalRequest
import re

router = APIRouter(prefix="/api")

class GoalRequest(BaseModel):
    goal: str = "Prepare Payments API for the next release. Find the current owner, explain the unresolved risk and the decision behind it, then coordinate the next investigation."
    project_id: str = "proj_payments_v2"
    workspace_id: str = DEFAULT_WORKSPACE_ID

class SupersedeRequest(BaseModel):
    workspace_id: str = DEFAULT_WORKSPACE_ID
    project_id: str = "proj_payments_v2"
    new_owner_id: str = "emp_eng_manager"
    announcement_text: Optional[str] = None

class GitHubIngestRequest(BaseModel):
    repo_url: str
    workspace_id: str = DEFAULT_WORKSPACE_ID
    max_files: int = 10
    ref: Optional[str] = None

class DocumentIngestRequest(BaseModel):
    title: str
    content: str
    path: Optional[str] = None
    project_name: Optional[str] = "Imported Documentation"
    workspace_id: str = DEFAULT_WORKSPACE_ID

class AskQuestionRequest(BaseModel):
    query: Optional[str] = None
    question: Optional[str] = None
    workspace_id: str = DEFAULT_WORKSPACE_ID

class GitHubHistoryImportRequest(BaseModel):
    repo_url: str
    workspace_id: str = DEFAULT_WORKSPACE_ID
    max_commits: int = 20
    max_pulls: int = 20
    max_issues: int = 20
    fetch_files: bool = True
    fetch_reviews: bool = True


@router.get("/health")
def health():
    return db_client.check_health()

@router.post("/reset")
def reset_demo(workspace_id: str = DEFAULT_WORKSPACE_ID):
    """Restore the clean preloaded demo state with zero login or setup."""
    db_client.reset_graph()
    stats = import_all_fixtures(workspace_id=workspace_id)
    return {
        "status": "RESET_SUCCESS",
        "message": "Demo workspace successfully reset to clean seeded state.",
        "stats": stats
    }

@router.get("/workspace")
def get_workspace_info(workspace_id: str = DEFAULT_WORKSPACE_ID):
    employees = get_all_employees(workspace_id)
    g = db_client.get_graph()
    node_count = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": workspace_id}).result_set[0][0]
    edge_count = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": workspace_id}).result_set[0][0]
    return {
        "workspace_id": workspace_id,
        "node_count": node_count,
        "edge_count": edge_count,
        "employees": employees,
        "synthetic_notice": "ALL DATA IS SYNTHETIC - SIMULATED SLACK, GITHUB, AND COMPANY WIKI"
    }

@router.get("/graph")
def get_graph(workspace_id: str = DEFAULT_WORKSPACE_ID):
    return get_graph_snapshot(workspace_id)

@router.get("/graph/stats")
def get_graph_stats(workspace_id: str = DEFAULT_WORKSPACE_ID):
    """Compatibility endpoint returning node and edge counts for the workspace graph."""
    g = db_client.get_graph()
    node_count = g.query("MATCH (n {workspace_id: $ws}) RETURN count(n)", {"ws": workspace_id}).result_set[0][0]
    edge_count = g.query("MATCH (a {workspace_id: $ws})-[r]->(b {workspace_id: $ws}) RETURN count(r)", {"ws": workspace_id}).result_set[0][0]
    return {
        "workspace_id": workspace_id,
        "node_count": node_count,
        "edge_count": edge_count
    }

@router.post("/workflow/run")
def run_workflow(req: GoalRequest):
    """Run the bounded multi-agent collaboration workflow for the given goal."""
    coordinator = Coordinator(workspace_id=req.workspace_id)
    result = coordinator.run_goal_workflow(goal_text=req.goal, project_id=req.project_id)
    return result

@router.get("/queries/owner")
def query_owner(workspace_id: str = DEFAULT_WORKSPACE_ID, project_id: str = "proj_payments_v2"):
    owner = get_current_owner(workspace_id, project_id)
    history = get_ownership_history(workspace_id, project_id)
    return {
        "current_owner": owner,
        "history": history
    }

@router.get("/queries/risks")
def query_risks(workspace_id: str = DEFAULT_WORKSPACE_ID, project_id: str = "proj_payments_v2"):
    return get_unresolved_risks(workspace_id, project_id)

@router.get("/queries/decisions")
def query_decisions(workspace_id: str = DEFAULT_WORKSPACE_ID, project_id: str = "proj_payments_v2"):
    return get_decisions_for_project(workspace_id, project_id)

@router.get("/queries/multi-hop")
def query_multi_hop(workspace_id: str = DEFAULT_WORKSPACE_ID, project_id: str = "proj_payments_v2"):
    return get_multi_hop_path(workspace_id, project_id)

@router.post("/freshness/supersede")
def supersede_fact(req: SupersedeRequest):
    announcement = req.announcement_text or "Marcus Chen (@marcus) has temporarily assumed operational ownership of Payments API v2 during release audit."
    res = supersede_ownership_fact(
        workspace_id=req.workspace_id,
        project_id=req.project_id,
        new_owner_id=req.new_owner_id,
        announcement_text=announcement
    )
    return res

@router.get("/memory/recall")
def recall_memory(workspace_id: str = DEFAULT_WORKSPACE_ID, query: str = "Payments"):
    return recall_cross_session_memory(workspace_id, query)

@router.get("/deliverable/latest")
def get_latest_deliverable(workspace_id: str = DEFAULT_WORKSPACE_ID):
    cypher = """
    MATCH (d:Deliverable {workspace_id: $ws})
    RETURN d.id, d.title, d.deliverable_type, d.status, d.content_json, d.owner_id, d.created_at
    ORDER BY d.created_at DESC LIMIT 1
    """
    rows = db_client.query(cypher, {"ws": workspace_id})
    if not rows:
        return {"deliverable": None}
    r = rows[0]
    return {
        "id": r[0],
        "title": r[1],
        "type": r[2],
        "status": r[3],
        "content": json.loads(r[4]) if r[4] else {},
        "owner_id": r[5],
        "created_at": r[6]
    }

@router.post("/generality/run")
def run_second_workflow(workspace_id: str = DEFAULT_WORKSPACE_ID):
    """P5 Generality Check: Run a second goal for Core Platform Infrastructure / Auth Gateway."""
    coordinator = Coordinator(workspace_id=workspace_id)
    goal = "Audit Core Platform Infrastructure dependencies and check Authentication Gateway readiness."
    result = coordinator.run_goal_workflow(goal_text=goal, project_id="proj_core_infra")
    return {
        "message": "Generality check successfully executed across non-payments company context.",
        "result": result
    }

@router.post("/ingest/github")
def ingest_github(req: GitHubIngestRequest):
    """Import public GitHub repository context without OAuth."""
    res = import_github_repo(
        req.repo_url,
        workspace_id=req.workspace_id,
        max_files=req.max_files,
        ref=req.ref
    )
    if res.get("status") == "INGESTION_FAILED":
        raise HTTPException(status_code=400, detail=res)
    return res

@router.post("/ingest/document")
def ingest_document(req: DocumentIngestRequest):
    """Import custom Markdown/text document into FalkorDB with grounded evidence chunks."""
    doc = {
        "title": req.title,
        "content": req.content,
        "path": req.path or req.title
    }
    proj_id = f"proj_doc_{re.sub(r'[^a-zA-Z0-9_]', '_', req.project_name.lower())}"
    res = store_imported_documents(
        documents=[doc],
        project_name=req.project_name,
        project_id=proj_id,
        source_type="IMPORTED_DOCUMENT",
        workspace_id=req.workspace_id
    )
    return res

@router.post("/ask")
def ask_question(req: AskQuestionRequest):
    """
    Answer an unseen question from the graph using ONLY retrieved evidence.
    If the graph has insufficient evidence, returns 'Not documented' and cites sources checked.
    Uses configured server-side model provider or honest direct graph retrieval.
    """
    q = req.query or req.question or ""
    return search_graph_evidence(workspace_id=req.workspace_id, query_text=q)

@router.post("/investigator/import")
@router.post("/contribution-investigator/import")
def import_repo_history(req: GitHubHistoryImportRequest):
    """
    Engineering Contribution Investigator: import bounded repository history
    (commits, pull requests, issues, touched files, reviews, and explicit issue resolutions).
    """
    res = import_github_engineering_history(
        repo_url=req.repo_url,
        workspace_id=req.workspace_id,
        max_commits=req.max_commits,
        max_pulls=req.max_pulls,
        max_issues=req.max_issues,
        fetch_files=req.fetch_files,
        fetch_reviews=req.fetch_reviews
    )
    if res.get("status") == "INGESTION_FAILED":
        raise HTTPException(status_code=400, detail=res)
    return res

@router.get("/investigator/contributions")
@router.get("/contribution-investigator/contributions")
def get_person_contributions_api(
    username: Optional[str] = Query(None, description="GitHub username/login, person ID, or name"),
    person: Optional[str] = Query(None, description="Alias for username"),
    workspace_id: str = DEFAULT_WORKSPACE_ID
):
    """
    Read-only query that lists a person's commits, PRs, reviews if available, and explicitly linked issues.
    """
    user_id = username or person
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing username or person query parameter")
    res = get_person_contributions(workspace_id=workspace_id, person_identifier=user_id)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail=res)
    return res

@router.post("/change-room/analyze")
def analyze_engineering_change(req: ChangeProposalRequest):
    """
    Company Brain: Engineering Change Room
    Evaluates proposed change: finds affected services, files, PRs, issues, current owner,
    architecture decisions, and affected documents using FalkorDB-backed agent communication.
    Creates a follow-up work task in FalkorDB assigned to the current technical owner.
    """
    change_room = EngineeringChangeRoom(workspace_id=req.workspace_id)
    return change_room.analyze_change(proposed_change=req.effective_change)

@router.post("/change-room/toggle-owner")
def toggle_owner_api(workspace_id: str = DEFAULT_WORKSPACE_ID):
    """
    Freshness Demo Action: Toggle the active technical owner between Asha Patel and Marcus Chen
    in FalkorDB to prove graph state is operational, not decoration.
    """
    return toggle_ownership_fact(workspace_id=workspace_id)

@router.get("/change-room/messages")
def get_change_messages(task_id: str = Query(..., description="Task ID to retrieve agent messages for"), workspace_id: str = DEFAULT_WORKSPACE_ID):
    """
    Retrieve durable AgentMessages exchanged between employee agents in FalkorDB for a given task.
    """
    messages = read_messages_for_task(workspace_id=workspace_id, task_id=task_id)
    return {"task_id": task_id, "messages": messages, "count": len(messages)}


