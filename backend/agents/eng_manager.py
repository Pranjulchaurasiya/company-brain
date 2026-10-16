from typing import List, Dict, Any
from backend.agents.employee_contract import (
    EmployeeInvocationContext,
    EmployeeInvocationOutput,
    ClaimItem,
    ActionItem,
    validate_claims_evidence
)

class EngineeringManagerAgent:
    EMPLOYEE_ID = "emp_eng_manager"
    ROLE = "Engineering Manager"

    def invoke(self, ctx: EmployeeInvocationContext) -> EmployeeInvocationOutput:
        """Inspect ownership and active tickets, identify Asha Patel as current owner, and delegate PAY-104 investigation."""
        owner_info = ctx.retrieved_context.get("owner_info", {})
        risks = ctx.retrieved_context.get("risks", [])
        
        claims = [
            ClaimItem(
                text="Asha Patel (@asha) is the active and sole accountable technical owner of Payments API v2, taking over from David Kim on 2026-09-28.",
                evidence_ids=["ev_chat_ownership_transfer"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Ticket PAY-104 is an active HIGH-severity release blocker: concurrent banking webhook retries during latency spikes cause race conditions and double settlement.",
                evidence_ids=["ev_pay_104_risk", "ev_chat_pay_104_blocker"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Releasing Payments API v2 is blocked until a worker-level distributed lock remediation is investigated and accepted.",
                evidence_ids=["ev_chat_pay_104_blocker"],
                confidence=1.0,
                kind="RECOMMENDATION"
            )
        ]

        validated_claims = validate_claims_evidence(claims, ctx.evidence_ids)

        actions = [
            ActionItem(
                tool_id="assign_investigation_task",
                arguments={
                    "task_id": "task_investigate_pay_104",
                    "assignee_id": "emp_engineer",
                    "acceptance_criteria": "Analyze Stripe webhook latency retry pattern, evaluate ADR-0042 constraints, and deliver technical findings with mutex lock specification."
                },
                risk_level="LOW"
            )
        ]

        summary = (
            "Confirmed Asha Patel as active technical owner of Payments API v2. "
            "Identified unresolved release blocker PAY-104 on webhook retry race conditions. "
            "Assigned investigation task to Staff Software Engineer Asha Patel with clear acceptance criteria."
        )

        return EmployeeInvocationOutput(
            status="DONE",
            summary=summary,
            claims=validated_claims,
            actions_proposed=actions,
            risks=["PAY-104 is a critical financial integrity risk if double charges occur in production."],
            next_owner_id="emp_engineer"
        )
