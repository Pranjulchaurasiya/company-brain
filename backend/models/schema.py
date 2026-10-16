from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class Employee(BaseModel):
    id: str
    workspace_id: str
    name: str
    title: str
    department: Optional[str] = None
    reports_to: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    status: str = "ACTIVE"

class Team(BaseModel):
    id: str
    workspace_id: str
    name: str
    purpose: str

class Skill(BaseModel):
    id: str
    workspace_id: str
    name: str

class Goal(BaseModel):
    id: str
    workspace_id: str
    title: str
    description: str
    status: str = "IN_PROGRESS"
    priority: str = "P0"
    created_by: str

class Project(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    status: str = "ACTIVE"
    source_id: Optional[str] = None

class Service(BaseModel):
    id: str
    workspace_id: str
    name: str
    environment: str = "PRODUCTION"
    status: str = "HEALTHY"
    source_id: Optional[str] = None

class Task(BaseModel):
    id: str
    workspace_id: str
    title: str
    description: str
    status: str = "READY_FOR_ASSIGNMENT" # READY_FOR_ASSIGNMENT, IN_PROGRESS, DONE, BLOCKED, FAILED
    priority: str = "P0"
    due_at: Optional[str] = None
    created_by: str
    assigned_to: Optional[str] = None
    goal_id: Optional[str] = None
    project_id: Optional[str] = None
    result: Optional[str] = None

class Document(BaseModel):
    id: str
    workspace_id: str
    title: str
    source_uri: str
    source_version: str = "1.0"
    source_updated_at: str

class Ticket(BaseModel):
    id: str
    workspace_id: str
    title: str
    status: str
    source_uri: str
    source_key: str
    source_updated_at: str
    severity: str = "MEDIUM"
    synthetic_label: str = "SIMULATED_GITHUB_ISSUE"

class ChatMessage(BaseModel):
    id: str
    workspace_id: str
    channel: str
    source_uri: str
    author_id: str
    author_name: Optional[str] = None
    source_created_at: str
    body: str
    synthetic_label: str = "SIMULATED_SLACK_CHANNEL"

class Decision(BaseModel):
    id: str
    workspace_id: str
    question: str
    outcome: str
    status: str = "ACCEPTED"
    decided_at: str
    decided_by: Optional[str] = None
    source_id: Optional[str] = None

class Evidence(BaseModel):
    id: str
    workspace_id: str
    excerpt: str
    locator: str # e.g. section, ticket key, chat message id
    captured_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_id: Optional[str] = None

class Fact(BaseModel):
    id: str
    workspace_id: str
    predicate: str # e.g. "OWNS_PROJECT", "OWNS_SERVICE", "HAS_RELEASE_RISK"
    value: str # e.g. "emp_engineer", "BLOCKED_ON_PAY_104"
    status: str = "ACTIVE" # ACTIVE, SUPERSEDED, RETRACTED, UNVERIFIED
    confidence: float = 1.0
    valid_from: str
    valid_until: Optional[str] = None
    observed_at: str
    extraction_method: str = "FIXTURE_INGESTION" # FIXTURE_INGESTION, AGENT_INFERENCE, USER_SPECIFIED
    subject_id: str
    object_id: str

class Source(BaseModel):
    id: str
    workspace_id: str
    source_type: str # DOCUMENT, TICKET, CHAT
    source_uri: str
    source_key: Optional[str] = None
    title: str
    author_id: Optional[str] = None
    source_created_at: Optional[str] = None
    source_updated_at: Optional[str] = None
    content_hash: Optional[str] = None

class AgentMessage(BaseModel):
    id: str
    workspace_id: str
    purpose: str
    body: str
    status: str = "SENT"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    correlation_id: Optional[str] = None
    from_employee_id: str
    to_employee_id: str
    task_id: Optional[str] = None

class Session(BaseModel):
    id: str
    workspace_id: str
    started_at: str
    ended_at: Optional[str] = None
    initiated_by: str

class Memory(BaseModel):
    id: str
    workspace_id: str
    memory_type: str # FINDING, DECISION, OWNER_CHANGE, RISK_ASSESSMENT
    content: str
    created_at: str
    valid_until: Optional[str] = None
    status: str = "ACTIVE" # ACTIVE, SUPERSEDED
    about_id: Optional[str] = None
    learned_from_task_id: Optional[str] = None
    evidence_id: Optional[str] = None

class Claim(BaseModel):
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    kind: Literal["FACT", "INFERENCE", "RECOMMENDATION", "UNKNOWN"] = "FACT"

class ActionProposed(BaseModel):
    tool_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"

class EmployeeInvocationResult(BaseModel):
    status: Literal["DONE", "NEEDS_INFO", "BLOCKED", "FAILED"]
    summary: str
    claims: List[Claim] = Field(default_factory=list)
    actions_proposed: List[ActionProposed] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    next_owner_id: Optional[str] = None

class HandoffRecord(BaseModel):
    task_id: str
    requesting_employee_id: str
    assigned_employee_id: str
    purpose: str
    relevant_entity_ids: List[str] = Field(default_factory=list)
    evidence_ids_already_found: List[str] = Field(default_factory=list)
    requested_output: str
    acceptance_criteria: str
    risks_or_approval_needed: Optional[str] = None

class Deliverable(BaseModel):
    id: str
    workspace_id: str
    title: str
    deliverable_type: str # e.g. "RELEASE_READINESS_BRIEF", "DECISION_RECORD"
    status: str = "COMPLETED"
    content: Dict[str, Any] = Field(default_factory=dict)
    owner_id: str
    project_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    evidence_ids: List[str] = Field(default_factory=list)
    task_ids: List[str] = Field(default_factory=list)
