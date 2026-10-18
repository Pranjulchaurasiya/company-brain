import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.config import DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client
from backend.db.queries import get_current_owner, get_ownership_history

logger = logging.getLogger("company_brain.freshness")

def supersede_ownership_fact(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    project_id: str = "proj_payments_v2",
    new_owner_id: str = "emp_eng_manager",
    announcement_text: str = "Marcus Chen (@marcus) has temporarily assumed operational ownership of Payments API v2 during release audit."
) -> Dict[str, Any]:
    """Demonstrate live fact supersession: Mark active fact as SUPERSEDED, create new ACTIVE fact, link SUPERSEDES, and update evidence."""
    now_iso = datetime.now(timezone.utc).isoformat()
    ts = int(datetime.now(timezone.utc).timestamp() * 1000000)

    # 1. Fetch current active fact
    active_rows = db_client.query("""
    MATCH (f:Fact {workspace_id: $ws, predicate: 'OWNS_PROJECT', status: 'ACTIVE'})-[:SUBJECT_PROJECT]->(p:Project {workspace_id: $ws, id: $proj})
    RETURN f.id, f.value
    """, {"ws": workspace_id, "proj": project_id})

    if not active_rows:
        raise ValueError(f"No active ownership fact found for project {project_id}")

    current_fact_id = active_rows[0][0]
    prior_owner_id = active_rows[0][1]

    # 2. Mark current fact as SUPERSEDED
    db_client.query("""
    MATCH (f:Fact {workspace_id: $ws, id: $fid})
    SET f.status = 'SUPERSEDED', f.valid_until = $now_iso
    """, {"ws": workspace_id, "fid": current_fact_id, "now_iso": now_iso})

    # 3. Create new Evidence and Chat Message representing the change event
    ev_id = f"ev_superseded_announcement_{ts}"
    msg_id = f"msg_superseded_{ts}"
    new_fact_id = f"fact_owner_superseded_{ts}"

    db_client.query("""
    MERGE (c:ChatMessage {workspace_id: $ws, id: $mid})
    ON CREATE SET c.channel = '#payments-rollout', c.source_uri = 'https://company-synthetic.slack.com/archives/C0812PAYROLL/p_update',
                  c.author_id = 'emp_chief_of_staff', c.source_created_at = $now_iso, c.body = $body, c.synthetic_label = 'SIMULATED_SLACK_CHANNEL'
    """, {"ws": workspace_id, "mid": msg_id, "now_iso": now_iso, "body": announcement_text})

    db_client.query("""
    MERGE (ev:Evidence {workspace_id: $ws, id: $evid})
    ON CREATE SET ev.excerpt = $excerpt, ev.locator = '#payments-rollout live update', ev.captured_at = $now_iso
    """, {"ws": workspace_id, "evid": ev_id, "excerpt": announcement_text, "now_iso": now_iso})

    db_client.query("""
    MATCH (s:Source {workspace_id: $ws, id: 'src_chat_rollout'})
    MATCH (ev:Evidence {workspace_id: $ws, id: $evid})
    MERGE (ev)-[:SUPPORTED_BY]->(s)
    """, {"ws": workspace_id, "evid": ev_id})

    # 4. Create new ACTIVE Fact
    db_client.query("""
    MERGE (f:Fact {workspace_id: $ws, id: $new_fid})
    ON CREATE SET f.predicate = 'OWNS_PROJECT', f.value = $new_owner, f.status = 'ACTIVE',
                  f.confidence = 1.0, f.valid_from = $now_iso, f.valid_until = null,
                  f.observed_at = $now_iso, f.extraction_method = 'DEMO_SUPERSESSION_ACTION'
    ON MATCH SET f.predicate = 'OWNS_PROJECT', f.value = $new_owner, f.status = 'ACTIVE',
                 f.valid_from = $now_iso, f.valid_until = null
    """, {"ws": workspace_id, "new_fid": new_fact_id, "new_owner": new_owner_id, "now_iso": now_iso})

    # 5. Link new Fact to Project, Employee, Evidence, Source, and link SUPERSEDES to prior fact
    db_client.query("""
    MATCH (f_new:Fact {workspace_id: $ws, id: $new_fid})
    MATCH (f_old:Fact {workspace_id: $ws, id: $old_fid})
    MATCH (p:Project {workspace_id: $ws, id: $proj})
    MATCH (e_new:Employee {workspace_id: $ws, id: $new_owner})
    MATCH (ev:Evidence {workspace_id: $ws, id: $evid})
    MATCH (s:Source {workspace_id: $ws, id: 'src_chat_rollout'})
    MERGE (f_new)-[:SUBJECT_PROJECT]->(p)
    MERGE (f_new)-[:OBJECT_EMPLOYEE]->(e_new)
    MERGE (f_new)-[:EVIDENCED_BY]->(ev)
    MERGE (f_new)-[:SUPPORTED_BY]->(s)
    MERGE (f_new)-[:SUPERSEDES]->(f_old)
    """, {
        "ws": workspace_id,
        "new_fid": new_fact_id,
        "old_fid": current_fact_id,
        "proj": project_id,
        "new_owner": new_owner_id,
        "evid": ev_id
    })

    logger.info(f"Fact '{current_fact_id}' (owner: {prior_owner_id}) successfully superseded by '{new_fact_id}' (new owner: {new_owner_id}).")

    return {
        "status": "SUPERSEDED_SUCCESS",
        "prior_fact_id": current_fact_id,
        "prior_owner_id": prior_owner_id,
        "new_fact_id": new_fact_id,
        "new_owner_id": new_owner_id,
        "superseded_at": now_iso,
        "evidence_id": ev_id,
        "updated_owner": get_current_owner(workspace_id, project_id),
        "history": get_ownership_history(workspace_id, project_id)
    }

def toggle_ownership_fact(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    project_id: str = "proj_payments_v2"
) -> Dict[str, Any]:
    """Toggle current active owner between Asha Patel (emp_engineer) and Marcus Chen (emp_eng_manager) to prove graph operational state."""
    owner_info = get_current_owner(workspace_id, project_id)
    current_emp_id = owner_info.get("employee_id") if owner_info else None

    if current_emp_id == "emp_engineer":
        new_owner_id = "emp_eng_manager"
        text = "Marcus Chen (@marcus) has assumed direct operational ownership of Payments API v2 and Payments Settlement Service."
    else:
        new_owner_id = "emp_engineer"
        text = "Asha Patel (@asha) has reassumed technical ownership of Payments API v2 and Payments Settlement Service."

    return supersede_ownership_fact(
        workspace_id=workspace_id,
        project_id=project_id,
        new_owner_id=new_owner_id,
        announcement_text=text
    )

def recall_cross_session_memory(
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    search_query: str = "Payments API"
) -> List[Dict[str, Any]]:
    """Retrieve prior workflow memories, findings, and decisions from FalkorDB in a fresh session with zero prompt history."""
    cypher = """
    MATCH (m:Memory {workspace_id: $ws, status: 'ACTIVE'})
    OPTIONAL MATCH (m)-[:ABOUT_PROJECT]->(p:Project)
    OPTIONAL MATCH (m)-[:LEARNED_FROM_TASK]->(t:Task)
    OPTIONAL MATCH (m)-[:EVIDENCED_BY]->(ev:Evidence)
    OPTIONAL MATCH (ev)-[:SUPPORTED_BY]->(s:Source)
    RETURN m.id, m.memory_type, m.content, m.created_at, p.id, p.name, t.id, t.title, ev.id, ev.excerpt, s.title, s.source_uri
    ORDER BY m.created_at DESC
    """
    rows = db_client.query(cypher, {"ws": workspace_id})
    mem_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        mid = r[0]
        if mid not in mem_map:
            mem_map[mid] = {
                "memory_id": mid,
                "type": r[1],
                "content": r[2],
                "created_at": r[3],
                "project": {"id": r[4], "name": r[5]} if r[4] else None,
                "originating_task": {"id": r[6], "title": r[7]} if r[6] else None,
                "evidence": {"id": r[8], "excerpt": r[9]} if r[8] else None,
                "source": {"title": r[10], "uri": r[11]} if r[10] else None,
                "evidence_citations": []
            }
        if r[8]:
            mem_map[mid]["evidence_citations"].append({
                "evidence_id": r[8],
                "excerpt": r[9],
                "source_title": r[10],
                "source_uri": r[11]
            })
    return list(mem_map.values())
