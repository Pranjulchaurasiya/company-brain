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
    task_id: Optional[str] = None
    sender_id: Optional[str] = None
    receiver_id: Optional[str] = None
    sender_agent: Optional[str] = None
    receiver_agent: Optional[str] = None
    from_employee_id: Optional[str] = None
    to_employee_id: Optional[str] = None
    message_type: str = "TASK_ASSIGNED"  # TASK_ASSIGNED, INVESTIGATION_RESULT, EVIDENCE_REQUEST, REVIEW_REQUEST, REVIEW_RESULT, APPROVAL_REQUIRED, TASK_COMPLETED, BLOCKED
    purpose: Optional[str] = None
    content: Optional[str] = None
    body: Optional[str] = None
    payload: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    requested_action: Optional[str] = None
    status: str = "SENT"  # SENT, DELIVERED, APPROVED, REJECTED, PROCESSED
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    correlation_id: Optional[str] = None

    def __init__(self, **data: Any):
        # Normalize sender/receiver and content/body/payload aliases
        sender = data.get("sender_agent") or data.get("sender_id") or data.get("from_employee_id")
        if sender:
            data["sender_agent"] = sender
            data["sender_id"] = sender
            data["from_employee_id"] = sender

        receiver = data.get("receiver_agent") or data.get("receiver_id") or data.get("to_employee_id")
        if receiver:
            data["receiver_agent"] = receiver
            data["receiver_id"] = receiver
            data["to_employee_id"] = receiver

        content_val = data.get("payload") or data.get("content") or data.get("body")
        if content_val:
            data["payload"] = content_val
            data["content"] = content_val
            data["body"] = content_val

        if "purpose" in data and not data.get("requested_action"):
            data["requested_action"] = data["purpose"]
        elif "requested_action" in data and not data.get("purpose"):
            data["purpose"] = data["requested_action"]

        super().__init__(**data)

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

class Repository(BaseModel):
    id: str
    workspace_id: str
    name: str
    full_name: str
    owner: str
    html_url: str
    default_branch: str = "main"
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class Person(BaseModel):
    id: str
    workspace_id: str
    login: str
    name: Optional[str] = None
    github_id: Optional[int] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None

class Commit(BaseModel):
    id: str
    workspace_id: str
    sha: str
    message: str
    author_login: Optional[str] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    authored_at: Optional[str] = None
    committed_at: Optional[str] = None
    html_url: str
    additions: int = 0
    deletions: int = 0
    total_changes: int = 0

class PullRequest(BaseModel):
    id: str
    workspace_id: str
    number: int
    title: str
    body: Optional[str] = None
    state: str
    is_merged: bool = False
    author_login: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    merged_at: Optional[str] = None
    html_url: str
    head_ref: Optional[str] = None
    base_ref: Optional[str] = None

class Issue(BaseModel):
    id: str
    workspace_id: str
    number: int
    title: str
    body: Optional[str] = None
    state: str
    state_reason: Optional[str] = None
    author_login: Optional[str] = None
    assignee_login: Optional[str] = None
    closed_by_login: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    html_url: str

class File(BaseModel):
    id: str
    workspace_id: str
    path: str
    filename: str
    extension: Optional[str] = None
    html_url: Optional[str] = None

from backend.config import DEFAULT_WORKSPACE_ID

class ChangeProposalRequest(BaseModel):
    proposed_change: Optional[str] = None
    change_request: Optional[str] = None
    question: Optional[str] = None
    query: Optional[str] = None
    proposed_files: Optional[List[str]] = None
    workspace_id: str = Field(default_factory=lambda: DEFAULT_WORKSPACE_ID)

    @property
    def effective_change(self) -> str:
        return self.proposed_change or self.change_request or self.question or self.query or "Replace Redis with Valkey in the Payments service."

class ImpactPathNode(BaseModel):
    type: str  # PROPOSED_CHANGE, SERVICE, FILE, PULL_REQUEST, ISSUE, OWNER, DECISION, TASK
    label: str
    id: Optional[str] = None
    url: Optional[str] = None
    provenance: Optional[str] = None

class GitHubIssueArtifact(BaseModel):
    title: str
    body: str
    assignees: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    html_url: Optional[str] = None
    state: str = "open"
    repository: Optional[str] = None
    task_id: Optional[str] = None

class ChangeImpactResponse(BaseModel):
    change_id: str
    proposed_change: str
    impact_path: List[ImpactPathNode] = Field(default_factory=list)
    impact_path_string: str
    affected_services: List[Dict[str, Any]] = Field(default_factory=list)
    affected_files: List[Dict[str, Any]] = Field(default_factory=list)
    related_pull_requests: List[Dict[str, Any]] = Field(default_factory=list)
    related_issues: List[Dict[str, Any]] = Field(default_factory=list)
    current_owner: Optional[Dict[str, Any]] = None
    previous_contributors: List[Dict[str, Any]] = Field(default_factory=list)
    architecture_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    affected_documents: List[Dict[str, Any]] = Field(default_factory=list)
    agent_messages: List[Dict[str, Any]] = Field(default_factory=list)
    verified_claims: List[Dict[str, Any]] = Field(default_factory=list)
    unproven_items: List[str] = Field(default_factory=list)
    followup_task: Optional[Dict[str, Any]] = None
    deliverable: Optional[Dict[str, Any]] = None
    final_answer: Optional[str] = None
    generated_github_issue: Optional[Dict[str, Any]] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    task_status_progression: List[str] = Field(default_factory=list)
    question_intent: Optional[str] = None


