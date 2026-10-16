from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class EmployeeInvocationContext(BaseModel):
    employee_id: str
    task_id: str
    goal_id: str
    role_instructions: str
    allowed_tool_ids: List[str] = Field(default_factory=list)
    retrieved_context: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    workspace_id: str

class ClaimItem(BaseModel):
    text: str
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    kind: Literal["FACT", "INFERENCE", "RECOMMENDATION", "UNKNOWN"] = "FACT"

class ActionItem(BaseModel):
    tool_id: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"

class EmployeeInvocationOutput(BaseModel):
    status: Literal["DONE", "NEEDS_INFO", "BLOCKED", "FAILED"]
    summary: str
    claims: List[ClaimItem] = Field(default_factory=list)
    actions_proposed: List[ActionItem] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    next_owner_id: Optional[str] = None
    deliverable_payload: Optional[Dict[str, Any]] = None

class HandoffMessage(BaseModel):
    task_id: str
    requesting_employee_id: str
    assigned_employee_id: str
    purpose: str
    relevant_entity_ids: List[str] = Field(default_factory=list)
    evidence_ids_already_found: List[str] = Field(default_factory=list)
    requested_output: str
    acceptance_criteria: str
    risks_or_approval_needed: Optional[str] = None
    timestamp: Optional[str] = None

def validate_claims_evidence(claims: List[ClaimItem], valid_evidence_ids: List[str]) -> List[ClaimItem]:
    """Ensure all cited evidence IDs actually exist in retrieved context. If invalid, downgrade or strip."""
    validated = []
    valid_set = set(valid_evidence_ids)
    for c in claims:
        filtered_ev = [eid for eid in c.evidence_ids if eid in valid_set]
        if c.kind == "FACT" and not filtered_ev:
            # Cannot assert fact without verified evidence
            validated.append(ClaimItem(
                text=f"{c.text} [Note: Unverified inference - no linked evidence]",
                evidence_ids=[],
                confidence=0.5,
                kind="INFERENCE"
            ))
        else:
            validated.append(ClaimItem(
                text=c.text,
                evidence_ids=filtered_ev,
                confidence=c.confidence,
                kind=c.kind
            ))
    return validated
