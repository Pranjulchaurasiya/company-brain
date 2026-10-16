from typing import List, Dict, Any
from backend.agents.employee_contract import (
    EmployeeInvocationContext,
    EmployeeInvocationOutput,
    ClaimItem,
    ActionItem,
    validate_claims_evidence
)

class EngineerAgent:
    EMPLOYEE_ID = "emp_engineer"
    ROLE = "Staff Software Engineer"

    def invoke(self, ctx: EmployeeInvocationContext) -> EmployeeInvocationOutput:
        """Investigate PAY-104 and ADR-0042, analyze race condition on webhook latency, and generate deliverable."""
        claims = [
            ClaimItem(
                text="ADR-0042 mandates client-side UUID idempotency keys with 48h caching, which prevents duplicate web checkout requests.",
                evidence_ids=["ev_adr_0042_rationale"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Asynchronous banking partner webhooks do not transmit client idempotency headers, so webhook retries during >800ms latency spikes bypass the ADR-0042 client-level guard.",
                evidence_ids=["ev_pay_104_risk", "ev_chat_pay_104_blocker"],
                confidence=1.0,
                kind="FACT"
            ),
            ClaimItem(
                text="Remediation: Implement a distributed Redis mutex keyed on 'lock:webhook:intent_id' with a 15-second TTL in Payments Settlement Service prior to processing transactions.",
                evidence_ids=["ev_pay_104_risk", "ev_adr_0042_rationale"],
                confidence=0.95,
                kind="RECOMMENDATION"
            )
        ]

        validated_claims = validate_claims_evidence(claims, ctx.evidence_ids)

        deliverable_content = {
            "title": "Payments API v2 Release-Readiness Assessment & Technical Remediation Plan",
            "project_id": "proj_payments_v2",
            "service_id": "svc_payments_settlement",
            "author_id": "emp_engineer",
            "author_name": "Asha Patel",
            "status": "COMPLETED_WITH_CONDITIONS",
            "readiness_verdict": "BLOCKED_PENDING_MUTEX_PR",
            "active_owner": "Asha Patel (Staff Software Engineer)",
            "key_findings": [
                "ADR-0042 covers client mutation idempotency but fails to protect asynchronous banking webhook retries.",
                "Ticket PAY-104 reproduced double authorization under upstream latency simulation (>800ms).",
                "Technical resolution: Introduce a distributed mutex lock on payment intent hashes before database transaction acquisition."
            ],
            "required_actions_before_signoff": [
                "Implement Redis distributed lock on payment intent references with 15s TTL in svc_payments_settlement.",
                "Execute webhook load-test with synthetic 1200ms latency injected.",
                "Knowledge Manager review to record updated architecture decision in FalkorDB."
            ],
            "sources_cited": [
                {"id": "doc_payments_brief_v2", "title": "Payments API v2 Release Brief", "type": "DOCUMENT"},
                {"id": "doc_adr_0042", "title": "ADR-0042: Mandating 48-Hour Idempotency Keys", "type": "DOCUMENT"},
                {"id": "tkt_pay_104", "title": "PAY-104: High-volume concurrent retries cause double settlement", "type": "TICKET"},
                {"id": "src_chat_rollout", "title": "Slack #payments-rollout Channel Transcript", "type": "CHAT"}
            ]
        }

        actions = [
            ActionItem(
                tool_id="persist_deliverable",
                arguments={
                    "deliverable_id": "deliv_payments_readiness_plan",
                    "title": deliverable_content["title"],
                    "deliverable_type": "RELEASE_READINESS_PLAN"
                },
                risk_level="LOW"
            )
        ]

        summary = (
            "Completed investigation of PAY-104 and ADR-0042. Diagnosed webhook latency race condition. "
            "Prepared technical remediation: 15s distributed Redis mutex barrier on transaction references. "
            "Compiled and saved release readiness deliverable."
        )

        return EmployeeInvocationOutput(
            status="DONE",
            summary=summary,
            claims=validated_claims,
            actions_proposed=actions,
            risks=["Without mutex implementation, production rollout risks duplicate customer settlements."],
            next_owner_id="emp_knowledge_mgr",
            deliverable_payload=deliverable_content
        )
