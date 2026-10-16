from typing import List, Dict, Any, Optional
from backend.db.falkordb_client import db_client

def get_current_owner(workspace_id: str, project_id: str = "proj_payments_v2") -> Optional[Dict[str, Any]]:
    """Retrieve current owner from active, non-superseded Facts linked to the project and employee."""
    cypher = """
    MATCH (f:Fact {workspace_id: $workspace_id, predicate: 'OWNS_PROJECT', status: 'ACTIVE'})-[:SUBJECT_PROJECT]->(p:Project {workspace_id: $workspace_id, id: $project_id})
    MATCH (f)-[:OBJECT_EMPLOYEE]->(e:Employee {workspace_id: $workspace_id})
    OPTIONAL MATCH (f)-[:EVIDENCED_BY]->(ev:Evidence)
    OPTIONAL MATCH (f)-[:SUPPORTED_BY]->(s:Source)
    RETURN e.id, e.name, e.title, e.department, f.id, f.valid_from, f.status, ev.id, ev.excerpt, ev.locator, s.id, s.title, s.source_type, s.source_uri
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "project_id": project_id})
    if not rows:
        return None
    r = rows[0]
    return {
        "employee_id": r[0],
        "name": r[1],
        "title": r[2],
        "department": r[3],
        "fact_id": r[4],
        "valid_from": r[5],
        "status": r[6],
        "evidence": {
            "id": r[7],
            "excerpt": r[8],
            "locator": r[9]
        } if r[7] else None,
        "source": {
            "id": r[10],
            "title": r[11],
            "type": r[12],
            "uri": r[13]
        } if r[10] else None
    }

def get_ownership_history(workspace_id: str, project_id: str = "proj_payments_v2") -> List[Dict[str, Any]]:
    """Retrieve both active and superseded ownership facts with provenance."""
    cypher = """
    MATCH (f:Fact {workspace_id: $workspace_id, predicate: 'OWNS_PROJECT'})-[:SUBJECT_PROJECT]->(p:Project {workspace_id: $workspace_id, id: $project_id})
    MATCH (f)-[:OBJECT_EMPLOYEE]->(e:Employee {workspace_id: $workspace_id})
    OPTIONAL MATCH (f)-[:EVIDENCED_BY]->(ev:Evidence)
    OPTIONAL MATCH (f)-[:SUPPORTED_BY]->(s:Source)
    OPTIONAL MATCH (f)-[:SUPERSEDES]->(prior:Fact)
    RETURN f.id, f.status, f.valid_from, f.valid_until, e.id, e.name, e.title, ev.id, ev.excerpt, s.title, prior.id
    ORDER BY f.valid_from DESC
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "project_id": project_id})
    history = []
    for r in rows:
        history.append({
            "fact_id": r[0],
            "status": r[1],
            "valid_from": r[2],
            "valid_until": r[3],
            "employee_id": r[4],
            "employee_name": r[5],
            "employee_title": r[6],
            "evidence_id": r[7],
            "evidence_excerpt": r[8],
            "source_title": r[9],
            "supersedes_fact_id": r[10]
        })
    return history

def get_unresolved_risks(workspace_id: str, project_id: str = "proj_payments_v2") -> List[Dict[str, Any]]:
    """Retrieve unresolved risks and blocking tickets connected to a project."""
    cypher = """
    MATCH (p:Project {workspace_id: $workspace_id, id: $project_id})-[:USES_SERVICE]->(s:Service)
    MATCH (t:Ticket {workspace_id: $workspace_id})-[:TRACKS_PROJECT]->(p)
    WHERE t.status IN ['BLOCKED', 'IN_PROGRESS', 'OPEN']
    OPTIONAL MATCH (e:Employee {workspace_id: $workspace_id}) WHERE e.id = t.assignee_id
    OPTIONAL MATCH (d:Decision {workspace_id: $workspace_id})-[:ABOUT_PROJECT]->(p)
    RETURN t.id, t.source_key, t.title, t.status, t.severity, t.source_uri, t.description,
           s.id, s.name, e.name, d.id, d.outcome
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "project_id": project_id})
    risks = []
    for r in rows:
        risks.append({
            "ticket_id": r[0],
            "ticket_key": r[1],
            "title": r[2],
            "status": r[3],
            "severity": r[4],
            "source_uri": r[5],
            "description": r[6],
            "service_id": r[7],
            "service_name": r[8],
            "assignee_name": r[9],
            "related_decision_id": r[10],
            "related_decision_outcome": r[11]
        })
    return risks

def get_decisions_for_project(workspace_id: str, project_id: str = "proj_payments_v2") -> List[Dict[str, Any]]:
    """Retrieve architectural decisions and rationales connected to a project."""
    cypher = """
    MATCH (d:Decision {workspace_id: $workspace_id})-[:ABOUT_PROJECT]->(p:Project {workspace_id: $workspace_id, id: $project_id})
    OPTIONAL MATCH (d)-[:MADE_BY]->(e:Employee)
    OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(s:Source)
    OPTIONAL MATCH (doc:Document {workspace_id: $workspace_id, id: d.source_id})
    RETURN d.id, d.question, d.outcome, d.status, d.decided_at, e.name, s.title, s.source_uri, doc.source_version
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "project_id": project_id})
    decisions = []
    for r in rows:
        decisions.append({
            "decision_id": r[0],
            "question": r[1],
            "outcome": r[2],
            "status": r[3],
            "decided_at": r[4],
            "decided_by": r[5],
            "source_title": r[6],
            "source_uri": r[7],
            "doc_version": r[8]
        })
    return decisions

def get_expertise_by_skill(workspace_id: str, skill_keyword: str) -> List[Dict[str, Any]]:
    """Find employee expertise by matching skills or prior ownership in FalkorDB."""
    cypher = """
    MATCH (e:Employee {workspace_id: $workspace_id})-[:HAS_SKILL]->(s:Skill {workspace_id: $workspace_id})
    WHERE toLower(s.name) CONTAINS toLower($skill_keyword)
    OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
    RETURN e.id, e.name, e.title, t.name, collect(s.name) as skills
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "skill_keyword": skill_keyword})
    experts = []
    for r in rows:
        experts.append({
            "employee_id": r[0],
            "name": r[1],
            "title": r[2],
            "team": r[3],
            "skills": r[4]
        })
    return experts

def get_multi_hop_path(workspace_id: str, project_id: str = "proj_payments_v2") -> Dict[str, Any]:
    """Retrieve multi-hop reasoning path: Project -> Service -> Risk/Ticket -> Decision -> Owner."""
    cypher = """
    MATCH (p:Project {workspace_id: $workspace_id, id: $project_id})-[:USES_SERVICE]->(s:Service)
    MATCH (t:Ticket {workspace_id: $workspace_id})-[:TRACKS_PROJECT]->(p)
    MATCH (d:Decision {workspace_id: $workspace_id})-[:ABOUT_PROJECT]->(p)
    MATCH (f:Fact {workspace_id: $workspace_id, predicate: 'OWNS_PROJECT', status: 'ACTIVE'})-[:SUBJECT_PROJECT]->(p)
    MATCH (f)-[:OBJECT_EMPLOYEE]->(owner:Employee)
    RETURN p.name, s.name, t.source_key + ': ' + t.title, d.outcome, owner.name, f.valid_from
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id, "project_id": project_id})
    if not rows:
        return {}
    r = rows[0]
    return {
        "project": r[0],
        "service": r[1],
        "unresolved_risk_ticket": r[2],
        "decision": r[3],
        "current_owner": r[4],
        "owner_effective_date": r[5],
        "relationship_path": f"Project({r[0]}) -[:USES_SERVICE]-> Service({r[1]}) -[:TRACKS_PROJECT]<- Ticket({r[2]}) -[:ABOUT_PROJECT]<- Decision({r[3]}) | ActiveOwner -> Employee({r[4]})"
    }

def get_all_employees(workspace_id: str) -> List[Dict[str, Any]]:
    cypher = """
    MATCH (e:Employee {workspace_id: $workspace_id})
    OPTIONAL MATCH (e)-[:MEMBER_OF]->(t:Team)
    OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
    OPTIONAL MATCH (e)-[:REPORTS_TO]->(mgr:Employee)
    RETURN e.id, e.name, e.title, e.department, t.name, mgr.name, collect(s.name)
    """
    rows = db_client.query(cypher, {"workspace_id": workspace_id})
    employees = []
    for r in rows:
        employees.append({
            "id": r[0],
            "name": r[1],
            "title": r[2],
            "department": r[3],
            "team": r[4],
            "reports_to_name": r[5],
            "skills": r[6]
        })
    return employees

def get_graph_snapshot(workspace_id: str) -> Dict[str, Any]:
    """Retrieve all nodes and edges for workspace to feed the visual graph canvas in the UI."""
    nodes_cypher = """
    MATCH (n {workspace_id: $workspace_id})
    RETURN labels(n) as labels, n.id as id, coalesce(n.name, n.title, n.source_key, n.predicate, n.id) as label, properties(n) as props
    """
    edges_cypher = """
    MATCH (source {workspace_id: $workspace_id})-[r]->(target {workspace_id: $workspace_id})
    RETURN type(r) as type, source.id as source, target.id as target, labels(source)[0] as source_label, labels(target)[0] as target_label
    """
    node_rows = db_client.query(nodes_cypher, {"workspace_id": workspace_id})
    edge_rows = db_client.query(edges_cypher, {"workspace_id": workspace_id})

    nodes = []
    for r in node_rows:
        labels = r[0] if isinstance(r[0], list) else [r[0]]
        nodes.append({
            "id": r[1],
            "label": r[2],
            "type": labels[0] if labels else "Entity",
            "properties": r[3]
        })

    edges = []
    for r in edge_rows:
        edges.append({
            "type": r[0],
            "source": r[1],
            "target": r[2],
            "source_type": r[3],
            "target_type": r[4]
        })

    return {"nodes": nodes, "edges": edges}
