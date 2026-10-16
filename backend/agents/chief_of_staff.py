from typing import List, Dict, Any
from backend.agents.employee_contract import (
    EmployeeInvocationContext,
    EmployeeInvocationOutput,
    ClaimItem,
    ActionItem,
    validate_claims_evidence
)

class ChiefOfStaffAgent:
    EMPLOYEE_ID = "emp_chief_of_staff"
    ROLE = "Chief of Staff"

    def invoke(self, ctx: EmployeeInvocationContext) -> EmployeeInvocationOutput:
        """Analyze user goal, review active projects from graph context, formulate plan, and delegate to Eng Manager."""
        projects = ctx.retrieved_context.get("projects", [])
        goal_title = ctx.retrieved_context.get("goal_title", "Company Goal")
        
        claims = [
            ClaimItem(
                text="The Payments API v2 initiative (proj_payments_v2) is scheduled for Q4 release readiness evaluation.",
                evidence_ids=["ev_brief_scope"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Operations requires accountable engineering sign-off on open release risks and architectural decisions before proceeding.",
                evidence_ids=["ev_brief_scope"],
                confidence=1.0,
                kind="FACT"
            )
        ]
        
        validated_claims = validate_claims_evidence(claims, ctx.evidence_ids)

        actions = [
            ActionItem(
                tool_id="task_assignment",
                arguments={
                    "task_id": "task_plan_payments_readiness",
                    "assignee_id": "emp_eng_manager",
                    "title": "Evaluate Payments API v2 readiness, verify ownership, and coordinate risk investigation"
                },
                risk_level="LOW"
            )
        ]

        summary = (
            f"Formulated structured execution plan for goal '{goal_title}'. "
            "Identified Payments API v2 as candidate release. Delegating ownership verification and "
            "risk investigation to Engineering Manager Marcus Chen."
        )

        return EmployeeInvocationOutput(
            status="DONE",
            summary=summary,
            claims=validated_claims,
            actions_proposed=actions,
            risks=["Unresolved release blockers may delay Q4 release timeline if distributed concurrency risks remain unmitigated."],
            next_owner_id="emp_eng_manager"
        )
