from ..core.base_agent import BaseAgent
from ..core.registry import AgentRegistry
import re
from typing import Dict, Any, List
from ..core.state import ExecutionState, AgentMessage
from ..tools.patient_records import order_repository_tool, policy_checker_tool, refund_gateway_tool

@AgentRegistry.register("supervisor_agent")
class SupervisorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SupervisorAgent",
            role_description="Decomposes clinical requests and coordinates sub-agents.",
            system_instruction="You are the Lead Clinical Orchestrator Agent. Analyze queries and formulate a multi-agent plan."
        )

@AgentRegistry.register("triage_sentiment_agent")
class TriageSentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="TriageSentimentAgent",
            role_description="Performs customer sentiment analysis and extracts order references.",
            system_instruction="You are an expert Customer Support Intake Agent. Extract order IDs and claim reasons."
        )

    def on_start(self, state: ExecutionState) -> None:
        match = re.search(r"\b(ORD-\d+|SUB-\d+)\b", state.user_query, re.IGNORECASE)
        order_id = match.group(1).upper() if match else (state.patient_id or "ORD-9921")
        state.context["order_id"] = order_id
        order_res = order_repository_tool.execute(order_id=order_id)
        if order_res.get("status") == "found":
            state.context["order_data"] = order_res["order"]
            state.record_audit("order_data_loaded", self.name, {"order_id": order_id})

@AgentRegistry.register("policy_audit_agent")
class PolicyAuditAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PolicyAuditAgent",
            role_description="Audits claims against 30-day policy and fraud thresholds.",
            system_instruction="You are the Enterprise Policy Auditor Agent. Enforce return windows and authorization thresholds."
        )

    def on_start(self, state: ExecutionState) -> None:
        order = state.context.get("order_data", {})
        if order:
            amount = order.get("total_amount", 0.0)
            eval_res = policy_checker_tool.execute(
                order_data=order,
                requested_amount=amount,
                customer_claim_reason=state.user_query
            )
            state.context["policy_evaluation"] = eval_res
            state.record_audit("policy_evaluated", self.name, eval_res)

@AgentRegistry.register("refund_resolution_agent")
class RefundResolutionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="RefundResolutionAgent",
            role_description="Executes refunds or prepares manager authorization request.",
            system_instruction="You are the Refund Settlement Agent. Issue refunds or trigger human manager gate."
        )

    def on_start(self, state: ExecutionState) -> None:
        policy = state.context.get("policy_evaluation", {})
        order = state.context.get("order_data", {})
        if policy.get("requires_human_approval"):
            state.needs_human_approval = True
            reasons = "; ".join(policy.get("approval_reasons", []))
            state.human_approval_reason = f"Manager approval required: {reasons}"
            state.record_audit("manager_gate_triggered", self.name, {"reasons": reasons})
        elif policy.get("is_policy_eligible"):
            refund_res = refund_gateway_tool.execute(
                order_id=order.get("order_id", "N/A"),
                amount=order.get("total_amount", 0.0),
                reason="Autonomous claim approved within standard policy",
                refund_type="full",
                approved_by="autonomous_agent"
            )
            state.context["refund_transaction"] = refund_res
            state.record_audit("refund_auto_settled", self.name, refund_res)

@AgentRegistry.register("support_response_agent")
class SupportResponseAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SupportResponseAgent",
            role_description="Drafts empathetic customer response.",
            system_instruction="You are the Customer Outreach Agent. Formulate clear, empathetic responses."
        )

    def on_finish(self, state: ExecutionState, message: AgentMessage) -> None:
        policy = state.context.get("policy_evaluation", {})
        order = state.context.get("order_data", {})
        tx = state.context.get("refund_transaction")
        cust_name = order.get("customer_name", "Valued Customer")
        order_id = order.get("order_id", "your order")

        lines = []
        if state.needs_human_approval:
            lines.append(f"**Status: Case Escalated for Finance / Support Manager Authorization**")
            lines.append(f"Dear {cust_name},\nThank you for contacting customer support regarding Order **{order_id}**.")
            lines.append(f"Because your claim involves high-value medical hardware or specific return conditions, your case has been escalated to our senior fulfillment team for fast-track authorization.")
            lines.append(f"**Escalation Reason**: {state.human_approval_reason}")
            lines.append(f"A manager has been notified and you will receive a binding confirmation shortly.")
        elif tx:
            lines.append(f"**Status: Refund Approved & Processed Automatically**")
            lines.append(f"Dear {cust_name},\nWe have processed your full refund for Order **{order_id}**.")
            lines.append(f"- **Refund Amount**: ${tx.get('amount_refunded'):.2f} {order.get('currency', 'USD')}")
            lines.append(f"- **Transaction Reference**: `{tx.get('refund_id')}`")
            lines.append(f"- **Method**: Original Payment Method (typically reflects within 3-5 business days).")
        else:
            lines.append(f"Dear {cust_name}, regarding order **{order_id}**: {message.content}")

        final_text = "\n\n".join(lines)
        message.content = final_text
        state.final_response = final_text
        state.is_completed = True
