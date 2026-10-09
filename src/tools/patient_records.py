from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from .base import BaseTool
from ..core.registry import ToolRegistry
from ..memory.vector_memory import vector_memory

# 1. Clinical Tools
@ToolRegistry.register("get_patient_ehr")
class PatientRecordsTool(BaseTool):
    SYNTHETIC_EHR_DB = {
        "PT-1001": {
            "patient_id": "PT-1001",
            "age": 58,
            "conditions": ["Hypertension", "Type 2 Diabetes Mellitus"],
            "active_medications": ["Metformin 1000mg BID", "Lisinopril 20mg Daily"],
            "allergies": ["Penicillin"]
        }
    }
    def __init__(self):
        super().__init__(name="get_patient_ehr", description="Retrieves patient EHR summary.")

    def execute(self, patient_id: str) -> Dict[str, Any]:
        patient = self.SYNTHETIC_EHR_DB.get(patient_id.upper())
        if not patient:
            return {"status": "not_found", "patient_id": patient_id}
        return {"status": "found", "patient": patient}

patient_records_tool = PatientRecordsTool()


@ToolRegistry.register("search_clinical_guidelines")
class ClinicalGuidelinesTool(BaseTool):
    def __init__(self):
        super().__init__(name="search_clinical_guidelines", description="Searches institutional clinical guidelines.")

    def execute(self, query: str, top_k: int = 2) -> Dict[str, Any]:
        results = vector_memory.search(query=query, top_k=top_k)
        return {"query": query, "matched_guidelines": results, "total_found": len(results)}

clinical_guidelines_tool = ClinicalGuidelinesTool()


@ToolRegistry.register("check_drug_interactions")
class DrugInteractionsTool(BaseTool):
    KNOWN_INTERACTIONS = [
        ("lisinopril", "spironolactone", "High Risk: Hyperkalemia danger.")
    ]
    def __init__(self):
        super().__init__(name="check_drug_interactions", description="Checks drug-drug interactions.")

    def execute(self, medications: List[str]) -> Dict[str, Any]:
        normalized = [m.lower().split()[0] for m in medications]
        flagged = []
        for d1, d2, warn in self.KNOWN_INTERACTIONS:
            if d1 in normalized and d2 in normalized:
                flagged.append({"drugs": [d1, d2], "severity": "HIGH", "clinical_warning": warn})
        return {"medications_checked": medications, "has_interactions": len(flagged) > 0, "interactions": flagged}

drug_interactions_tool = DrugInteractionsTool()


# 2. E-Commerce & SaaS Dispute Resolution Tools
@ToolRegistry.register("get_order_details")
class OrderRepositoryTool(BaseTool):
    ORDERS_DB = {
        "ORD-9921": {
            "order_id": "ORD-9921",
            "customer_name": "Sarah Jenkins",
            "customer_email": "s.jenkins@example.com",
            "order_date": "2026-10-01T10:14:00Z",
            "items": [{"sku": "MED-GLUC-01", "name": "Continuous Glucose Monitor Sensor (Pack of 2)", "price": 145.00, "condition_required": "unopened_seal"}],
            "total_amount": 145.00,
            "currency": "USD",
            "payment_status": "settled",
            "fulfillment_status": "delivered",
            "delivery_date": "2026-10-04T15:20:00Z",
            "carrier_tracking": "USPS-94001118992231001",
            "dispute_history_count": 0
        },
        "ORD-7740": {
            "order_id": "ORD-7740",
            "customer_name": "Marcus Vance",
            "customer_email": "m.vance@example.com",
            "order_date": "2026-08-10T12:00:00Z",
            "items": [{"sku": "MED-BP-PRO", "name": "Smart Blood Pressure Monitor", "price": 89.99, "condition_required": "any"}],
            "total_amount": 89.99,
            "currency": "USD",
            "payment_status": "settled",
            "fulfillment_status": "delivered",
            "delivery_date": "2026-08-14T11:00:00Z",
            "carrier_tracking": "FEDEX-782299102911",
            "dispute_history_count": 3
        },
        "SUB-3312": {
            "order_id": "SUB-3312",
            "customer_name": "Elena Rostova",
            "customer_email": "elena.r@example.com",
            "order_date": "2026-10-07T08:00:00Z",
            "items": [{"sku": "SAAS-TELEHEALTH-MO", "name": "Telehealth Concierge Monthly Plan", "price": 49.00, "condition_required": "pro_rated_available"}],
            "total_amount": 49.00,
            "currency": "USD",
            "payment_status": "settled",
            "fulfillment_status": "digital_provisioned",
            "delivery_date": "2026-10-07T08:00:00Z",
            "carrier_tracking": "N/A_DIGITAL",
            "dispute_history_count": 0
        }
    }
    def __init__(self):
        super().__init__(name="get_order_details", description="Retrieves order items, delivery dates, and dispute history.")

    def execute(self, order_id: str) -> Dict[str, Any]:
        key = order_id.upper().strip()
        rec = self.ORDERS_DB.get(key)
        if not rec:
            return {"status": "not_found", "order_id": order_id}
        return {"status": "found", "order": rec}

order_repository_tool = OrderRepositoryTool()


@ToolRegistry.register("process_refund_transaction")
class RefundGatewayTool(BaseTool):
    def __init__(self):
        super().__init__(name="process_refund_transaction", description="Processes financial refund through payment processor.")

    def execute(self, order_id: str, amount: float, reason: str, refund_type: str = "full", approved_by: str = "system") -> Dict[str, Any]:
        tx_id = f"re_{uuid.uuid4().hex[:12]}"
        return {
            "status": "settled",
            "refund_id": tx_id,
            "order_id": order_id,
            "amount_refunded": amount,
            "reason": reason,
            "approved_by": approved_by,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

refund_gateway_tool = RefundGatewayTool()


@ToolRegistry.register("check_refund_policy")
class PolicyCheckerTool(BaseTool):
    def __init__(self):
        super().__init__(name="check_refund_policy", description="Evaluates return eligibility against 30-day window and amount thresholds.")

    def execute(self, order_data: Dict[str, Any], requested_amount: float, customer_claim_reason: str) -> Dict[str, Any]:
        violations = []
        is_eligible = True
        requires_approval = False
        reasons = []

        if requested_amount > 50.00:
            requires_approval = True
            reasons.append(f"Amount ${requested_amount:.2f} exceeds autonomous settlement cap ($50.00)")

        disputes = order_data.get("dispute_history_count", 0)
        if disputes >= 2:
            requires_approval = True
            reasons.append(f"Customer account has elevated dispute risk ({disputes} previous charge disputes)")

        deliv_str = order_data.get("delivery_date")
        if deliv_str:
            try:
                deliv_dt = datetime.fromisoformat(deliv_str.replace("Z", "+00:00"))
                days = (datetime.now(timezone.utc) - deliv_dt).days
                if days > 30:
                    is_eligible = False
                    violations.append(f"Return window expired ({days} days since delivery; maximum allowed is 30 days)")
            except Exception:
                pass

        return {
            "is_policy_eligible": is_eligible,
            "requires_human_approval": requires_approval or (not is_eligible),
            "approval_reasons": reasons,
            "policy_violations": violations,
            "assessed_amount": requested_amount
        }

policy_checker_tool = PolicyCheckerTool()
