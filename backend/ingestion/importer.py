import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.config import FIXTURES_DIR, DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client

logger = logging.getLogger("company_brain.importer")

def run_cypher_merge(cypher: str, params: Dict[str, Any]) -> None:
    try:
        db_client.query(cypher, params)
    except Exception as e:
        logger.error(f"Error in cypher: {cypher[:100]}... params: {params} => {e}")
        raise

def import_all_fixtures(workspace_id: str = DEFAULT_WORKSPACE_ID) -> Dict[str, Any]:
    """Ingest all synthetic documents, tickets, chat records, employees, and facts idempotently."""
    logger.info(f"Starting idempotent ingestion for workspace '{workspace_id}'...")
    db_client.init_schema()

    stats = {
        "employees": 0,
        "teams": 0,
        "skills": 0,
        "projects": 0,
        "services": 0,
        "goals": 0,
        "tasks": 0,
        "documents": 0,
        "tickets": 0,
        "chat_messages": 0,
        "decisions": 0,
        "facts": 0,
        "sources": 0,
        "evidence": 0,
        "memories": 0
    }

    # 1. Employees & Skills
    emp_file = FIXTURES_DIR / "employees.json"
    if emp_file.exists():
        with open(emp_file, "r", encoding="utf-8") as f:
            employees = json.load(f)
        for emp in employees:
            # Merge Employee node
            run_cypher_merge("""
            MERGE (e:Employee {workspace_id: $workspace_id, id: $id})
            ON CREATE SET e.name = $name, e.title = $title, e.department = $department, e.status = $status
            ON MATCH SET e.name = $name, e.title = $title, e.department = $department, e.status = $status
            """, {
                "workspace_id": workspace_id,
                "id": emp["id"],
                "name": emp["name"],
                "title": emp["title"],
                "department": emp.get("department", "Engineering"),
                "status": emp.get("status", "ACTIVE")
            })
            stats["employees"] += 1

            # Skills
            for skill_name in emp.get("skills", []):
                skill_id = f"skill_{skill_name.lower().replace(' ', '_').replace('-', '_')}"
                run_cypher_merge("""
                MERGE (s:Skill {workspace_id: $workspace_id, id: $id})
                ON CREATE SET s.name = $name
                ON MATCH SET s.name = $name
                """, {"workspace_id": workspace_id, "id": skill_id, "name": skill_name})
                run_cypher_merge("""
                MATCH (e:Employee {workspace_id: $workspace_id, id: $emp_id})
                MATCH (s:Skill {workspace_id: $workspace_id, id: $skill_id})
                MERGE (e)-[:HAS_SKILL]->(s)
                """, {"workspace_id": workspace_id, "emp_id": emp["id"], "skill_id": skill_id})
                stats["skills"] += 1

        # Reports-to relationships
        for emp in employees:
            if emp.get("reports_to"):
                run_cypher_merge("""
                MATCH (e:Employee {workspace_id: $workspace_id, id: $emp_id})
                MATCH (mgr:Employee {workspace_id: $workspace_id, id: $mgr_id})
                MERGE (e)-[:REPORTS_TO]->(mgr)
                """, {"workspace_id": workspace_id, "emp_id": emp["id"], "mgr_id": emp["reports_to"]})

    # 1.1 Guarantee the 6 canonical Employee-Agent nodes exist with :Employee:Agent labels
    canonical_employee_agents = [
        {"id": "emp_chief_of_staff", "name": "Elena Vance", "title": "Chief of Staff", "role": "Coordinator", "department": "Leadership & Strategy"},
        {"id": "emp_engineer", "name": "Asha Patel", "title": "Staff Software Engineer", "role": "Code Investigator", "department": "Platform Engineering"},
        {"id": "emp_eng_manager", "name": "Marcus Chen", "title": "Engineering Manager", "role": "Ownership Agent", "department": "Platform Engineering"},
        {"id": "emp_knowledge_mgr", "name": "Sophia Wu", "title": "Knowledge Manager", "role": "Knowledge Agent", "department": "Technical Operations"},
        {"id": "emp_reviewer", "name": "Dr. Aris Thorne", "title": "Reviewer", "role": "Reviewer", "department": "Quality & Verification"},
        {"id": "emp_execution_agent", "name": "Jordan Bell", "title": "Execution Agent", "role": "Execution Agent", "department": "Engineering Operations"},
    ]
    for ag in canonical_employee_agents:
        run_cypher_merge("""
        MERGE (a:Employee {workspace_id: $workspace_id, id: $id})
        ON CREATE SET a.name = $name, a.title = $title, a.role = $role, a.department = $dept, a.status = 'ACTIVE'
        ON MATCH SET a.name = $name, a.title = $title, a.role = $role
        """, {
            "workspace_id": workspace_id,
            "id": ag["id"],
            "name": ag["name"],
            "title": ag["title"],
            "role": ag["role"],
            "dept": ag["department"]
        })
        run_cypher_merge("""
        MATCH (a:Employee {workspace_id: $workspace_id, id: $id})
        SET a:Agent
        """, {"workspace_id": workspace_id, "id": ag["id"]})

    # Also register role-based Agent nodes as aliases
    agent_aliases = [
        ("emp_coordinator", "emp_chief_of_staff", "Coordinator"),
        ("emp_code_investigator", "emp_engineer", "Code Investigator"),
        ("emp_ownership_agent", "emp_eng_manager", "Ownership Agent"),
        ("emp_knowledge_agent", "emp_knowledge_mgr", "Knowledge Agent"),
    ]
    for alias_id, target_id, role in agent_aliases:
        run_cypher_merge("""
        MERGE (a:Agent {workspace_id: $workspace_id, id: $alias_id})
        ON CREATE SET a.role = $role, a.target_id = $target_id
        ON MATCH SET a.role = $role, a.target_id = $target_id
        """, {"workspace_id": workspace_id, "alias_id": alias_id, "target_id": target_id, "role": role})
        run_cypher_merge("""
        MATCH (a:Agent {workspace_id: $workspace_id, id: $alias_id})
        MATCH (e:Employee {workspace_id: $workspace_id, id: $target_id})
        MERGE (a)-[:ACTS_FOR]->(e)
        """, {"workspace_id": workspace_id, "alias_id": alias_id, "target_id": target_id})

    # 2. Company Entities (Teams, Projects, Services, Goals, Tasks, Decisions)
    ent_file = FIXTURES_DIR / "company_entities.json"
    if ent_file.exists():
        with open(ent_file, "r", encoding="utf-8") as f:
            entities = json.load(f)

        for team in entities.get("teams", []):
            run_cypher_merge("""
            MERGE (t:Team {workspace_id: $workspace_id, id: $id})
            ON CREATE SET t.name = $name, t.purpose = $purpose
            ON MATCH SET t.name = $name, t.purpose = $purpose
            """, {"workspace_id": workspace_id, "id": team["id"], "name": team["name"], "purpose": team["purpose"]})
            stats["teams"] += 1

        # Connect employees to teams
        run_cypher_merge("""
        MATCH (e:Employee {workspace_id: $workspace_id})
        MATCH (t:Team {workspace_id: $workspace_id})
        WHERE (e.department = 'Platform Engineering' AND t.id = 'team_platform')
           OR (e.department = 'Operations & Leadership' AND t.id = 'team_operations')
           OR (e.department = 'Technical Operations' AND t.id = 'team_tech_ops')
           OR (e.department = 'Core Systems' AND t.id = 'team_core_systems')
        MERGE (e)-[:MEMBER_OF]->(t)
        """, {"workspace_id": workspace_id})

        for proj in entities.get("projects", []):
            run_cypher_merge("""
            MERGE (p:Project {workspace_id: $workspace_id, id: $id})
            ON CREATE SET p.name = $name, p.description = $description, p.status = $status, p.source_id = $source_id
            ON MATCH SET p.name = $name, p.description = $description, p.status = $status, p.source_id = $source_id
            """, {
                "workspace_id": workspace_id,
                "id": proj["id"],
                "name": proj["name"],
                "description": proj["description"],
                "status": proj["status"],
                "source_id": proj.get("source_id")
            })
            stats["projects"] += 1

        for svc in entities.get("services", []):
            run_cypher_merge("""
            MERGE (s:Service {workspace_id: $workspace_id, id: $id})
            ON CREATE SET s.name = $name, s.environment = $environment, s.status = $status, s.source_id = $source_id
            ON MATCH SET s.name = $name, s.environment = $environment, s.status = $status, s.source_id = $source_id
            """, {
                "workspace_id": workspace_id,
                "id": svc["id"],
                "name": svc["name"],
                "environment": svc["environment"],
                "status": svc["status"],
                "source_id": svc.get("source_id")
            })
            stats["services"] += 1

        # Project uses Service
        run_cypher_merge("""
        MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
        MATCH (s:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MERGE (p)-[:USES_SERVICE]->(s)
        """, {"workspace_id": workspace_id})

        # Seed Payments core code, PR, and Issue nodes for change room investigation
        run_cypher_merge("""
        MERGE (f:File {workspace_id: $workspace_id, id: 'file_payments_redis_client'})
        ON CREATE SET f.path = 'services/payments/redis_client.py', f.filename = 'redis_client.py',
                      f.extension = '.py', f.html_url = 'https://github.com/company-synthetic/payments-core/blob/main/services/payments/redis_client.py'
        ON MATCH SET f.path = 'services/payments/redis_client.py', f.filename = 'redis_client.py',
                     f.extension = '.py', f.html_url = 'https://github.com/company-synthetic/payments-core/blob/main/services/payments/redis_client.py'
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MERGE (iss:Issue {workspace_id: $workspace_id, id: 'issue_payments_31'})
        ON CREATE SET iss.number = 31, iss.title = 'Race condition in payment settlement webhook retry handler (PAY-104)',
                      iss.source_key = 'PAY-104', iss.state = 'OPEN',
                      iss.html_url = 'https://github.com/company-synthetic/payments-core/issues/31',
                      iss.created_at = '2026-10-02T14:22:00Z', iss.assignee_login = 'asha', iss.closed_by_login = null
        ON MATCH SET iss.number = 31, iss.title = 'Race condition in payment settlement webhook retry handler (PAY-104)',
                     iss.source_key = 'PAY-104', iss.state = 'OPEN',
                     iss.html_url = 'https://github.com/company-synthetic/payments-core/issues/31'
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MERGE (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        ON CREATE SET pr.number = 42, pr.title = 'Implement Redis distributed mutex lock for transaction settlement (Fixes #31)',
                      pr.state = 'MERGED', pr.is_merged = true, pr.author_login = 'asha',
                      pr.created_at = '2026-10-03T11:00:00Z', pr.merged_at = '2026-10-04T15:30:00Z',
                      pr.html_url = 'https://github.com/company-synthetic/payments-core/pull/42',
                      pr.body = 'Implements ADR-0042 idempotency lock with 5s Redis mutex. Fixes #31'
        ON MATCH SET pr.number = 42, pr.title = 'Implement Redis distributed mutex lock for transaction settlement (Fixes #31)',
                     pr.state = 'MERGED', pr.is_merged = true, pr.author_login = 'asha',
                     pr.html_url = 'https://github.com/company-synthetic/payments-core/pull/42',
                     pr.body = 'Implements ADR-0042 idempotency lock with 5s Redis mutex. Fixes #31'
        """, {"workspace_id": workspace_id})



        for goal in entities.get("goals", []):
            run_cypher_merge("""
            MERGE (g:Goal {workspace_id: $workspace_id, id: $id})
            ON CREATE SET g.title = $title, g.description = $description, g.status = $status, g.priority = $priority, g.created_by = $created_by
            ON MATCH SET g.title = $title, g.description = $description, g.status = $status, g.priority = $priority, g.created_by = $created_by
            """, {
                "workspace_id": workspace_id,
                "id": goal["id"],
                "title": goal["title"],
                "description": goal["description"],
                "status": goal["status"],
                "priority": goal["priority"],
                "created_by": goal["created_by"]
            })
            stats["goals"] += 1
            run_cypher_merge("""
            MATCH (g:Goal {workspace_id: $workspace_id, id: $goal_id})
            MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
            MERGE (g)-[:DRIVES]->(p)
            """, {"workspace_id": workspace_id, "goal_id": goal["id"]})

        for task in entities.get("tasks", []):
            run_cypher_merge("""
            MERGE (t:Task {workspace_id: $workspace_id, id: $id})
            ON CREATE SET t.title = $title, t.description = $description, t.status = $status, t.priority = $priority, t.due_at = $due_at, t.created_by = $created_by
            ON MATCH SET t.title = $title, t.description = $description, t.status = $status, t.priority = $priority, t.due_at = $due_at, t.created_by = $created_by
            """, {
                "workspace_id": workspace_id,
                "id": task["id"],
                "title": task["title"],
                "description": task["description"],
                "status": task["status"],
                "priority": task["priority"],
                "due_at": task.get("due_at"),
                "created_by": task["created_by"]
            })
            stats["tasks"] += 1
            run_cypher_merge("""
            MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
            MATCH (t:Task {workspace_id: $workspace_id, id: $task_id})
            MERGE (p)-[:HAS_TASK]->(t)
            """, {"workspace_id": workspace_id, "task_id": task["id"]})

        for dec in entities.get("decisions", []):
            run_cypher_merge("""
            MERGE (d:Decision {workspace_id: $workspace_id, id: $id})
            ON CREATE SET d.question = $question, d.outcome = $outcome, d.status = $status, d.decided_at = $decided_at, d.decided_by = $decided_by, d.source_id = $source_id
            ON MATCH SET d.question = $question, d.outcome = $outcome, d.status = $status, d.decided_at = $decided_at, d.decided_by = $decided_by, d.source_id = $source_id
            """, {
                "workspace_id": workspace_id,
                "id": dec["id"],
                "question": dec["question"],
                "outcome": dec["outcome"],
                "status": dec["status"],
                "decided_at": dec["decided_at"],
                "decided_by": dec.get("decided_by"),
                "source_id": dec.get("source_id")
            })
            stats["decisions"] += 1
            run_cypher_merge("""
            MATCH (d:Decision {workspace_id: $workspace_id, id: $dec_id})
            MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
            MERGE (d)-[:ABOUT_PROJECT]->(p)
            """, {"workspace_id": workspace_id, "dec_id": dec["id"]})
            if dec.get("decided_by"):
                run_cypher_merge("""
                MATCH (d:Decision {workspace_id: $workspace_id, id: $dec_id})
                MATCH (e:Employee {workspace_id: $workspace_id, id: $emp_id})
                MERGE (d)-[:MADE_BY]->(e)
                """, {"workspace_id": workspace_id, "dec_id": dec["id"], "emp_id": dec["decided_by"]})

        # Connect Payments core code, PR, Issue, Employee, and Decision
        run_cypher_merge("""
        MATCH (s:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MATCH (f:File {workspace_id: $workspace_id, id: 'file_payments_redis_client'})
        MERGE (s)-[:HAS_FILE]->(f)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (s:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MATCH (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        MERGE (s)-[:HAS_PULL_REQUEST]->(pr)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (s:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MATCH (iss:Issue {workspace_id: $workspace_id, id: 'issue_payments_31'})
        MERGE (s)-[:HAS_ISSUE]->(iss)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        MATCH (f:File {workspace_id: $workspace_id, id: 'file_payments_redis_client'})
        MERGE (pr)-[:TOUCHED_FILE]->(f)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        MATCH (iss:Issue {workspace_id: $workspace_id, id: 'issue_payments_31'})
        MERGE (pr)-[:RESOLVES_ISSUE]->(iss)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (e:Employee {workspace_id: $workspace_id, id: 'emp_engineer'})
        MATCH (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        MERGE (e)-[:OPENED_PR]->(pr)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (dec:Decision {workspace_id: $workspace_id, id: 'dec_adr_0042'})
        MATCH (s:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MERGE (dec)-[:AFFECTS_SERVICE]->(s)
        """, {"workspace_id": workspace_id})

        run_cypher_merge("""
        MATCH (dec:Decision {workspace_id: $workspace_id, id: 'dec_adr_0042'})
        MATCH (pr:PullRequest {workspace_id: $workspace_id, id: 'pr_payments_42'})
        MERGE (dec)-[:REFERENCED_BY_PR]->(pr)
        """, {"workspace_id": workspace_id})

    # 3. Documents (Release Brief & ADR-0042)
    brief_file = FIXTURES_DIR / "payments_release_brief.md"
    if brief_file.exists():
        content = brief_file.read_text(encoding="utf-8")
        run_cypher_merge("""
        MERGE (s:Source {workspace_id: $workspace_id, id: 'src_doc_payments_brief'})
        ON CREATE SET s.source_type = 'DOCUMENT', s.title = 'Payments API v2 Release Brief', s.source_uri = 'doc://company-wiki/engineering/payments/v2-release-brief.md', s.source_updated_at = '2026-10-01T10:00:00Z'
        ON MATCH SET s.source_type = 'DOCUMENT', s.title = 'Payments API v2 Release Brief', s.source_uri = 'doc://company-wiki/engineering/payments/v2-release-brief.md', s.source_updated_at = '2026-10-01T10:00:00Z'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (d:Document {workspace_id: $workspace_id, id: 'doc_payments_brief_v2'})
        ON CREATE SET d.title = 'Payments API v2 Release Brief', d.source_uri = 'doc://company-wiki/engineering/payments/v2-release-brief.md', d.source_version = '2.1', d.source_updated_at = '2026-10-01T10:00:00Z'
        ON MATCH SET d.title = 'Payments API v2 Release Brief', d.source_uri = 'doc://company-wiki/engineering/payments/v2-release-brief.md', d.source_version = '2.1', d.source_updated_at = '2026-10-01T10:00:00Z'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MATCH (s:Source {workspace_id: $workspace_id, id: 'src_doc_payments_brief'})
        MATCH (d:Document {workspace_id: $workspace_id, id: 'doc_payments_brief_v2'})
        MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
        MERGE (s)-[:SOURCE_DOCUMENT]->(d)
        MERGE (d)-[:DESCRIBES_PROJECT]->(p)
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_brief_scope'})
        ON CREATE SET ev.excerpt = 'The Payments API v2 initiative (proj_payments_v2) modernizes the core transaction processing stack for high-throughput global checkouts.', ev.locator = 'Section: Executive Summary'
        ON MATCH SET ev.excerpt = 'The Payments API v2 initiative (proj_payments_v2) modernizes the core transaction processing stack for high-throughput global checkouts.', ev.locator = 'Section: Executive Summary'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_brief_scope'})
        MATCH (s:Source {workspace_id: $workspace_id, id: 'src_doc_payments_brief'})
        MERGE (ev)-[:SUPPORTED_BY]->(s)
        """, {"workspace_id": workspace_id})
        stats["documents"] += 1
        stats["sources"] += 1
        stats["evidence"] += 1

    adr_file = FIXTURES_DIR / "adr_0042_idempotency_keys.md"
    if adr_file.exists():
        run_cypher_merge("""
        MERGE (s:Source {workspace_id: $workspace_id, id: 'src_doc_adr_0042'})
        ON CREATE SET s.source_type = 'DOCUMENT', s.title = 'ADR-0042: Mandating 48-Hour Idempotency Keys on Payment Settlement', s.source_uri = 'doc://company-wiki/architecture/adr-0042-payment-idempotency.md', s.source_updated_at = '2026-09-15T16:30:00Z'
        ON MATCH SET s.source_type = 'DOCUMENT', s.title = 'ADR-0042: Mandating 48-Hour Idempotency Keys on Payment Settlement', s.source_uri = 'doc://company-wiki/architecture/adr-0042-payment-idempotency.md', s.source_updated_at = '2026-09-15T16:30:00Z'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (d:Document {workspace_id: $workspace_id, id: 'doc_adr_0042'})
        ON CREATE SET d.title = 'ADR-0042: Mandating 48-Hour Idempotency Keys', d.source_uri = 'doc://company-wiki/architecture/adr-0042-payment-idempotency.md', d.source_version = '1.0', d.source_updated_at = '2026-09-15T16:30:00Z'
        ON MATCH SET d.title = 'ADR-0042: Mandating 48-Hour Idempotency Keys', d.source_uri = 'doc://company-wiki/architecture/adr-0042-payment-idempotency.md', d.source_version = '1.0', d.source_updated_at = '2026-09-15T16:30:00Z'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_adr_0042_rationale'})
        ON CREATE SET ev.excerpt = 'We mandate an explicit 48-hour idempotency key strategy across all write operations on svc_payments_settlement to eliminate duplicate authorization races.', ev.locator = 'Section: Decision Rationale'
        ON MATCH SET ev.excerpt = 'We mandate an explicit 48-hour idempotency key strategy across all write operations on svc_payments_settlement to eliminate duplicate authorization races.', ev.locator = 'Section: Decision Rationale'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MATCH (dec:Decision {workspace_id: $workspace_id, id: 'dec_adr_0042'})
        MATCH (s:Source {workspace_id: $workspace_id, id: 'src_doc_adr_0042'})
        MATCH (d:Document {workspace_id: $workspace_id, id: 'doc_adr_0042'})
        MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_adr_0042_rationale'})
        MERGE (s)-[:SOURCE_DOCUMENT]->(d)
        MERGE (dec)-[:SUPPORTED_BY]->(s)
        MERGE (ev)-[:SUPPORTED_BY]->(s)
        """, {"workspace_id": workspace_id})
        stats["documents"] += 1
        stats["sources"] += 1
        stats["evidence"] += 1

    # 4. Ticket PAY-104
    tkt_file = FIXTURES_DIR / "ticket_pay_104.json"
    if tkt_file.exists():
        with open(tkt_file, "r", encoding="utf-8") as f:
            tkt = json.load(f)
        run_cypher_merge("""
        MERGE (s:Source {workspace_id: $workspace_id, id: 'src_ticket_pay_104'})
        ON CREATE SET s.source_type = 'TICKET', s.source_key = $key, s.source_uri = $uri, s.title = $title, s.source_created_at = $created_at, s.source_updated_at = $updated_at
        ON MATCH SET s.source_type = 'TICKET', s.source_key = $key, s.source_uri = $uri, s.title = $title, s.source_created_at = $created_at, s.source_updated_at = $updated_at
        """, {
            "workspace_id": workspace_id,
            "key": tkt["source_key"],
            "uri": tkt["source_uri"],
            "title": tkt["title"],
            "created_at": tkt["source_created_at"],
            "updated_at": tkt["source_updated_at"]
        })
        run_cypher_merge("""
        MERGE (t:Ticket {workspace_id: $workspace_id, id: $id})
        ON CREATE SET t.source_key = $key, t.title = $title, t.status = $status, t.source_uri = $uri, t.severity = $severity, t.source_updated_at = $updated_at, t.description = $desc, t.synthetic_label = $syn_label, t.assignee_id = $assignee_id
        ON MATCH SET t.source_key = $key, t.title = $title, t.status = $status, t.source_uri = $uri, t.severity = $severity, t.source_updated_at = $updated_at, t.description = $desc, t.synthetic_label = $syn_label, t.assignee_id = $assignee_id
        """, {
            "workspace_id": workspace_id,
            "id": tkt["id"],
            "key": tkt["source_key"],
            "title": tkt["title"],
            "status": tkt["status"],
            "uri": tkt["source_uri"],
            "severity": tkt.get("severity", "HIGH"),
            "updated_at": tkt["source_updated_at"],
            "desc": tkt["description"],
            "syn_label": tkt.get("synthetic_label", "SIMULATED_GITHUB_ISSUE"),
            "assignee_id": tkt.get("assignee_id")
        })
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_pay_104_risk'})
        ON CREATE SET ev.excerpt = $excerpt, ev.locator = 'Ticket PAY-104 Description'
        ON MATCH SET ev.excerpt = $excerpt, ev.locator = 'Ticket PAY-104 Description'
        """, {"workspace_id": workspace_id, "excerpt": tkt["description"]})
        run_cypher_merge("""
        MATCH (s:Source {workspace_id: $workspace_id, id: 'src_ticket_pay_104'})
        MATCH (t:Ticket {workspace_id: $workspace_id, id: $tkt_id})
        MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
        MATCH (svc:Service {workspace_id: $workspace_id, id: 'svc_payments_settlement'})
        MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_pay_104_risk'})
        MERGE (s)-[:SOURCE_TICKET]->(t)
        MERGE (t)-[:TRACKS_PROJECT]->(p)
        MERGE (t)-[:TRACKS_SERVICE]->(svc)
        MERGE (ev)-[:SUPPORTED_BY]->(s)
        """, {"workspace_id": workspace_id, "tkt_id": tkt["id"]})
        stats["tickets"] += 1
        stats["sources"] += 1
        stats["evidence"] += 1

    # 5. Chat Transcript
    chat_file = FIXTURES_DIR / "chat_payments_rollout.json"
    if chat_file.exists():
        with open(chat_file, "r", encoding="utf-8") as f:
            chat_data = json.load(f)
        run_cypher_merge("""
        MERGE (s:Source {workspace_id: $workspace_id, id: 'src_chat_rollout'})
        ON CREATE SET s.source_type = 'CHAT', s.source_uri = $uri, s.title = 'Slack #payments-rollout Channel Transcript', s.source_updated_at = '2026-10-05T16:22:00Z'
        ON MATCH SET s.source_type = 'CHAT', s.source_uri = $uri, s.title = 'Slack #payments-rollout Channel Transcript', s.source_updated_at = '2026-10-05T16:22:00Z'
        """, {"workspace_id": workspace_id, "uri": chat_data["source_uri"]})
        stats["sources"] += 1

        for msg in chat_data.get("messages", []):
            run_cypher_merge("""
            MERGE (c:ChatMessage {workspace_id: $workspace_id, id: $id})
            ON CREATE SET c.channel = $channel, c.source_uri = $uri, c.author_id = $author_id, c.author_name = $author_name, c.source_created_at = $created_at, c.body = $body, c.synthetic_label = $syn_label
            ON MATCH SET c.channel = $channel, c.source_uri = $uri, c.author_id = $author_id, c.author_name = $author_name, c.source_created_at = $created_at, c.body = $body, c.synthetic_label = $syn_label
            """, {
                "workspace_id": workspace_id,
                "id": msg["id"],
                "channel": chat_data["channel"],
                "uri": f"{chat_data['source_uri']}#{msg['id']}",
                "author_id": msg["author_id"],
                "author_name": msg.get("author_name"),
                "created_at": msg["source_created_at"],
                "body": msg["body"],
                "syn_label": chat_data.get("synthetic_label", "SIMULATED_SLACK_CHANNEL")
            })
            run_cypher_merge("""
            MATCH (s:Source {workspace_id: $workspace_id, id: 'src_chat_rollout'})
            MATCH (c:ChatMessage {workspace_id: $workspace_id, id: $msg_id})
            MERGE (s)-[:SOURCE_CHAT]->(c)
            """, {"workspace_id": workspace_id, "msg_id": msg["id"]})
            stats["chat_messages"] += 1

        # Evidence records from chat
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_chat_ownership_transfer'})
        ON CREATE SET ev.excerpt = 'Effective today 2026-09-28, Asha Patel (@asha) is taking over as the official technical and operational owner of Payments API v2 and Payments Settlement Service.', ev.locator = '#payments-rollout msg_chat_002'
        ON MATCH SET ev.excerpt = 'Effective today 2026-09-28, Asha Patel (@asha) is taking over as the official technical and operational owner of Payments API v2 and Payments Settlement Service.', ev.locator = '#payments-rollout msg_chat_002'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_chat_legacy_owner'})
        ON CREATE SET ev.excerpt = 'I am currently managing the Payments API legacy architecture and Payments Settlement Service while we spec out v2.', ev.locator = '#payments-rollout msg_chat_001'
        ON MATCH SET ev.excerpt = 'I am currently managing the Payments API legacy architecture and Payments Settlement Service while we spec out v2.', ev.locator = '#payments-rollout msg_chat_001'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MERGE (ev:Evidence {workspace_id: $workspace_id, id: 'ev_chat_pay_104_blocker'})
        ON CREATE SET ev.excerpt = 'PAY-104 is an active release risk. ADR-0042 solved client idempotency with headers, but banking webhook retries arrive asynchronously before initial transactions finish committing. Releasing Payments v2 is unsafe without worker-level mutex.', ev.locator = '#payments-rollout msg_chat_005'
        ON MATCH SET ev.excerpt = 'PAY-104 is an active release risk. ADR-0042 solved client idempotency with headers, but banking webhook retries arrive asynchronously before initial transactions finish committing. Releasing Payments v2 is unsafe without worker-level mutex.', ev.locator = '#payments-rollout msg_chat_005'
        """, {"workspace_id": workspace_id})
        run_cypher_merge("""
        MATCH (s:Source {workspace_id: $workspace_id, id: 'src_chat_rollout'})
        MATCH (ev1:Evidence {workspace_id: $workspace_id, id: 'ev_chat_ownership_transfer'})
        MATCH (ev2:Evidence {workspace_id: $workspace_id, id: 'ev_chat_legacy_owner'})
        MATCH (ev3:Evidence {workspace_id: $workspace_id, id: 'ev_chat_pay_104_blocker'})
        MERGE (ev1)-[:SUPPORTED_BY]->(s)
        MERGE (ev2)-[:SUPPORTED_BY]->(s)
        MERGE (ev3)-[:SUPPORTED_BY]->(s)
        """, {"workspace_id": workspace_id})
        stats["evidence"] += 3

    # 6. Facts (Active and Superseded Ownership Facts with Provenance)
    # Prior Fact: David Kim owned Payments v2 prior to Sept 28
    run_cypher_merge("""
    MERGE (f:Fact {workspace_id: $workspace_id, id: 'fact_owner_legacy_david'})
    ON CREATE SET f.predicate = 'OWNS_PROJECT', f.value = 'emp_prior_dev', f.status = 'SUPERSEDED', f.confidence = 1.0, f.valid_from = '2026-08-15T14:10:00Z', f.valid_until = '2026-09-28T09:30:00Z', f.observed_at = '2026-08-15T14:10:00Z', f.extraction_method = 'FIXTURE_INGESTION'
    ON MATCH SET f.predicate = 'OWNS_PROJECT', f.value = 'emp_prior_dev', f.status = 'SUPERSEDED', f.confidence = 1.0, f.valid_from = '2026-08-15T14:10:00Z', f.valid_until = '2026-09-28T09:30:00Z', f.observed_at = '2026-08-15T14:10:00Z', f.extraction_method = 'FIXTURE_INGESTION'
    """, {"workspace_id": workspace_id})
    run_cypher_merge("""
    MATCH (f:Fact {workspace_id: $workspace_id, id: 'fact_owner_legacy_david'})
    MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
    MATCH (e:Employee {workspace_id: $workspace_id, id: 'emp_prior_dev'})
    MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_chat_legacy_owner'})
    MATCH (s:Source {workspace_id: $workspace_id, id: 'src_chat_rollout'})
    MERGE (f)-[:SUBJECT_PROJECT]->(p)
    MERGE (f)-[:OBJECT_EMPLOYEE]->(e)
    MERGE (f)-[:EVIDENCED_BY]->(ev)
    MERGE (f)-[:SUPPORTED_BY]->(s)
    """, {"workspace_id": workspace_id})

    # Active Current Fact: Asha Patel owns Payments v2 from Sept 28 onwards
    run_cypher_merge("""
    MERGE (f:Fact {workspace_id: $workspace_id, id: 'fact_owner_current_asha'})
    ON CREATE SET f.predicate = 'OWNS_PROJECT', f.value = 'emp_engineer', f.status = 'ACTIVE', f.confidence = 1.0, f.valid_from = '2026-09-28T09:30:00Z', f.valid_until = null, f.observed_at = '2026-09-28T09:30:00Z', f.extraction_method = 'FIXTURE_INGESTION'
    ON MATCH SET f.predicate = 'OWNS_PROJECT', f.value = 'emp_engineer', f.status = 'ACTIVE', f.confidence = 1.0, f.valid_from = '2026-09-28T09:30:00Z', f.valid_until = null, f.observed_at = '2026-09-28T09:30:00Z', f.extraction_method = 'FIXTURE_INGESTION'
    """, {"workspace_id": workspace_id})
    run_cypher_merge("""
    MATCH (f:Fact {workspace_id: $workspace_id, id: 'fact_owner_current_asha'})
    MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
    MATCH (e:Employee {workspace_id: $workspace_id, id: 'emp_engineer'})
    MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_chat_ownership_transfer'})
    MATCH (s:Source {workspace_id: $workspace_id, id: 'src_chat_rollout'})
    MATCH (f_old:Fact {workspace_id: $workspace_id, id: 'fact_owner_legacy_david'})
    MERGE (f)-[:SUBJECT_PROJECT]->(p)
    MERGE (f)-[:OBJECT_EMPLOYEE]->(e)
    MERGE (f)-[:EVIDENCED_BY]->(ev)
    MERGE (f)-[:SUPPORTED_BY]->(s)
    MERGE (f)-[:SUPERSEDES]->(f_old)
    """, {"workspace_id": workspace_id})
    stats["facts"] += 2

    # 7. Durable Session and Memory records
    run_cypher_merge("""
    MERGE (sess:Session {workspace_id: $workspace_id, id: 'sess_init_seed'})
    ON CREATE SET sess.started_at = '2026-10-10T12:00:00Z', sess.ended_at = '2026-10-10T12:30:00Z', sess.initiated_by = 'emp_chief_of_staff'
    ON MATCH SET sess.started_at = '2026-10-10T12:00:00Z', sess.ended_at = '2026-10-10T12:30:00Z', sess.initiated_by = 'emp_chief_of_staff'
    """, {"workspace_id": workspace_id})

    run_cypher_merge("""
    MERGE (m:Memory {workspace_id: $workspace_id, id: 'mem_adr_0042_finding'})
    ON CREATE SET m.memory_type = 'FINDING', m.content = 'ADR-0042 mandates client UUID idempotency, but banking webhook retries still require an in-worker distributed mutex lock on payment intent references before Payments v2 rollout is safe.', m.created_at = '2026-10-10T12:05:00Z', m.status = 'ACTIVE'
    ON MATCH SET m.memory_type = 'FINDING', m.content = 'ADR-0042 mandates client UUID idempotency, but banking webhook retries still require an in-worker distributed mutex lock on payment intent references before Payments v2 rollout is safe.', m.created_at = '2026-10-10T12:05:00Z', m.status = 'ACTIVE'
    """, {"workspace_id": workspace_id})
    run_cypher_merge("""
    MATCH (m:Memory {workspace_id: $workspace_id, id: 'mem_adr_0042_finding'})
    MATCH (p:Project {workspace_id: $workspace_id, id: 'proj_payments_v2'})
    MATCH (ev:Evidence {workspace_id: $workspace_id, id: 'ev_adr_0042_rationale'})
    MATCH (s:Source {workspace_id: $workspace_id, id: 'src_doc_adr_0042'})
    MERGE (m)-[:ABOUT_PROJECT]->(p)
    MERGE (m)-[:EVIDENCED_BY]->(ev)
    MERGE (m)-[:SUPPORTED_BY]->(s)
    """, {"workspace_id": workspace_id})
    stats["memories"] += 1

    logger.info(f"Ingestion completed successfully for workspace '{workspace_id}'. Stats: {stats}")
    return stats
