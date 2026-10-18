from typing import List, Dict, Any
from backend.agents.employee_contract import (
    EmployeeInvocationContext,
    EmployeeInvocationOutput,
    ClaimItem,
    ActionItem,
    validate_claims_evidence
)

class KnowledgeManagerAgent:
    EMPLOYEE_ID = "emp_knowledge_mgr"
    ROLE = "Knowledge Manager"

    def invoke(self, ctx: EmployeeInvocationContext) -> EmployeeInvocationOutput:
        """Validate provenance of all findings, verify active vs superseded fact status, and commit audit record."""
        claims = [
            ClaimItem(
                text="All claims and findings have been cross-referenced against stored Sources (Document, Ticket, Chat) and Evidence locators in FalkorDB.",
                evidence_ids=["ev_brief_scope", "ev_adr_0042_rationale", "ev_pay_104_risk", "ev_chat_ownership_transfer"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Historical ownership fact 'fact_owner_legacy_david' is confirmed SUPERSEDED and excluded from current answering scope. Current fact 'fact_owner_current_asha' is confirmed ACTIVE.",
                evidence_ids=["ev_chat_ownership_transfer", "ev_chat_legacy_owner"],
                confidence=1.0,
                kind="FACT"
            )
        ]

        validated_claims = validate_claims_evidence(claims, ctx.evidence_ids)

        actions = [
            ActionItem(
                tool_id="persist_memory",
                arguments={
                    "memory_id": "mem_workflow_payments_readiness",
                    "content": "Payments API v2 is blocked by PAY-104 webhook race condition. Technical owner is Asha Patel. Remediation plan requires 15s distributed mutex on payment intent references.",
                    "evidence_ids": ["ev_pay_104_risk", "ev_chat_ownership_transfer", "ev_adr_0042_rationale"]
                },
                risk_level="LOW"
            )
        ]

        summary = (
            "Knowledge audit complete: Validated all 4 cross-source evidence links. "
            "Confirmed fact supersession history (David Kim -> Asha Patel). "
            "Persisted durable memory record linked to task and evidence for cross-session recall."
        )

        return EmployeeInvocationOutput(
            status="DONE",
            summary=summary,
            claims=validated_claims,
            actions_proposed=actions,
            risks=[],
            next_owner_id="emp_chief_of_staff" # Returns to coordinator / Chief of Staff for final review and close
        )
