from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional

from .config import settings
from .workflows.healthcare_flow import customer_support_workflow, healthcare_workflow
from .memory.session_memory import session_memory
from .observability.tracker import tracker
from .core.registry import AgentRegistry, ToolRegistry

from .agents.supervisor import (
    SupervisorAgent,
    TriageSentimentAgent,
    PolicyAuditAgent,
    RefundResolutionAgent,
    SupportResponseAgent
)
from .tools.patient_records import (
    order_repository_tool,
    policy_checker_tool,
    refund_gateway_tool,
    patient_records_tool,
    clinical_guidelines_tool,
    drug_interactions_tool
)

app = FastAPI(
    title="Clinical E-Commerce & SaaS AI Dispute Platform",
    description="Production Multi-Agent Platform for Automated Customer Support & Dispute Resolution",
    version="2.0.0"
)

class SupportChatRequest(BaseModel):
    query: str = Field(..., description="Customer dispute inquiry or refund request")
    order_id: Optional[str] = Field(None, description="Optional Order ID (e.g., ORD-9921, SUB-3312, ORD-7740)")
    session_id: Optional[str] = Field(None, description="Session ID for continuous context")

class ManagerApprovalRequest(BaseModel):
    session_id: str
    approved: bool
    manager_notes: Optional[str] = None

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": "Clinical E-Commerce & SaaS Support Agent",
        "environment": settings.app_env
    }

@app.get("/api/v1/agents")
def list_registered_agents():
    return {"registered_agents": list(AgentRegistry.list_agents().keys())}

@app.get("/api/v1/tools")
def list_registered_tools():
    return {"registered_tools": list(ToolRegistry.list_tools().keys())}

@app.get("/api/v1/telemetry")
def get_telemetry():
    return tracker.get_summary()

@app.post("/api/v1/chat")
def process_chat(req: SupportChatRequest):
    try:
        state = customer_support_workflow.run(
            user_query=req.query,
            order_id=req.order_id,
            session_id=req.session_id
        )
        return {
            "session_id": state.session_id,
            "final_response": state.final_response,
            "needs_human_approval": state.needs_human_approval,
            "human_approval_reason": state.human_approval_reason,
            "guardrail_flags": state.guardrail_flags,
            "order_data": state.context.get("order_data"),
            "refund_transaction": state.context.get("refund_transaction"),
            "policy_evaluation": state.context.get("policy_evaluation"),
            "messages": [m.to_dict() for m in state.messages],
            "audit_trail_count": len(state.audit_log)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/session/{session_id}")
def get_session(session_id: str):
    state = session_memory.get_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.to_dict()

@app.post("/api/v1/human-approval")
def submit_manager_approval(req: ManagerApprovalRequest):
    state = session_memory.get_state(req.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    order = state.context.get("order_data", {})
    name = order.get("customer_name", "Customer")
    oid = order.get("order_id", "your order")

    if req.approved:
        tx = refund_gateway_tool.execute(
            order_id=order.get("order_id", "N/A"),
            amount=order.get("total_amount", 0.0),
            reason=f"Manager authorized: {req.manager_notes or 'Approved by Support Director'}",
            approved_by="support_manager"
        )
        state.context["refund_transaction"] = tx
        state.needs_human_approval = False
        state.final_response = (
            f"**[Manager Approved & Refund Issued]**\n\n"
            f"Dear {name},\n"
            f"Your refund of **${tx.get('amount_refunded', 0):.2f}** for Order **{oid}** has been approved by a manager and settled.\n"
            f"- **Transaction ID**: `{tx.get('refund_id')}`\n"
            f"- **Manager Note**: {req.manager_notes or 'Authorized per customer satisfaction policy'}\n"
            f"- Funds will reflect on your card within 3-5 business days."
        )
    else:
        state.needs_human_approval = False
        state.final_response = (
            f"**[Manager Decision: Refund Claim Rejected]**\n\n"
            f"Dear {name},\n"
            f"Following manager review of Order **{oid}**, your refund request could not be approved.\n"
            f"- **Reason**: {req.manager_notes or 'Item outside 30-day policy / non-returnable sterile supply.'}\n"
            f"If you have further documentation, please reply to this case."
        )

    state.record_audit(
        action="manager_approval_recorded",
        agent="SupportManager",
        details={"approved": req.approved, "notes": req.manager_notes}
    )
    session_memory.save_state(state)
    return {
        "status": "success",
        "session_id": req.session_id,
        "approved": req.approved,
        "updated_response": state.final_response
    }

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Commerce Dispute & Auto-Refund AI Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        .chat-scroll::-webkit-scrollbar { width: 6px; }
        .chat-scroll::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
    </style>
</head>
<body class="bg-slate-100 text-slate-800 font-sans antialiased h-screen flex flex-col">

    <header class="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between shadow-sm flex-shrink-0">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white text-lg shadow-md shadow-indigo-500/20">
                <i class="fa-solid fa-headset"></i>
            </div>
            <div>
                <h1 class="font-bold text-base text-slate-900 leading-tight">Clinical Commerce AI</h1>
                <p class="text-xs text-slate-500">Autonomous Support, Policy Audit & Refund Gatekeeper (Google ADK)</p>
            </div>
        </div>
        <div class="flex items-center space-x-3">
            <span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span class="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span>
                Autonomous Policy Engine Active
            </span>
            <a href="/docs" target="_blank" class="text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-1 rounded border border-slate-200">
                <i class="fa-solid fa-code mr-1"></i>Swagger API
            </a>
        </div>
    </header>

    <div class="flex-1 flex overflow-hidden max-w-7xl w-full mx-auto p-4 gap-4">
        
        <aside class="w-80 flex-shrink-0 flex flex-col gap-4">
            
            <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <label class="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                    <i class="fa-solid fa-box-open mr-1 text-indigo-500"></i> Selected Order Context
                </label>
                <select id="orderSelect" onchange="updateOrderPreview()" class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-xs font-medium focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                    <option value="ORD-9921" selected>ORD-9921 ($145.00) - Glucose Sensor (8 days ago)</option>
                    <option value="SUB-3312">SUB-3312 ($49.00) - Telehealth SaaS (2 days ago)</option>
                    <option value="ORD-7740">ORD-7740 ($89.99) - Blood Pressure (60 days ago - EXPIRED)</option>
                </select>

                <div id="orderPreviewBox" class="mt-3 text-xs bg-slate-50 p-2.5 rounded-lg border border-slate-100 text-slate-600 space-y-1">
                    <div><b>Customer:</b> Sarah Jenkins</div>
                    <div><b>Item:</b> Continuous Glucose Monitor (Pack of 2)</div>
                    <div><b>Delivered:</b> Oct 4 (8 days ago)</div>
                    <div><b>Auto-Refund Policy:</b> > $50 triggers Manager Gate</div>
                </div>
            </div>

            <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex-1 flex flex-col">
                <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                    <i class="fa-solid fa-network-wired mr-1 text-indigo-500"></i> Multi-Agent Pipeline
                </h3>
                <div class="space-y-2 text-xs flex-1">
                    <div id="agent-triage" class="p-2 rounded-lg border border-slate-100 bg-slate-50 flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid fa-comments text-blue-500"></i>
                            <span class="font-medium">1. Triage & Sentiment</span>
                        </div>
                        <span class="badge text-[10px] text-slate-400">Ready</span>
                    </div>
                    <div id="agent-policy" class="p-2 rounded-lg border border-slate-100 bg-slate-50 flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid fa-scale-balanced text-purple-500"></i>
                            <span class="font-medium">2. Policy & 30-Day Check</span>
                        </div>
                        <span class="badge text-[10px] text-slate-400">Ready</span>
                    </div>
                    <div id="agent-resolution" class="p-2 rounded-lg border border-slate-100 bg-slate-50 flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid fa-hand-holding-dollar text-emerald-500"></i>
                            <span class="font-medium">3. Settlement Gatekeeper</span>
                        </div>
                        <span class="badge text-[10px] text-slate-400">Ready</span>
                    </div>
                    <div id="agent-response" class="p-2 rounded-lg border border-slate-100 bg-slate-50 flex items-center justify-between">
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid fa-envelope-open-text text-amber-500"></i>
                            <span class="font-medium">4. Customer Outreach</span>
                        </div>
                        <span class="badge text-[10px] text-slate-400">Ready</span>
                    </div>
                </div>

                <div class="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500 flex justify-between">
                    <span>Processed: <b id="tokensNum" class="text-slate-700">0</b> tokens</span>
                    <span>Cost: <b id="costNum" class="text-slate-700">$0.0000</b></span>
                </div>
            </div>
        </aside>

        <main class="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden">
            
            <div class="p-2.5 bg-slate-50 border-b border-slate-200 flex items-center gap-2 overflow-x-auto text-xs flex-shrink-0">
                <span class="text-slate-400 font-medium whitespace-nowrap"><i class="fa-regular fa-lightbulb mr-1"></i>Try:</span>
                <button onclick="pickPrompt('My package for ORD-9921 was damaged in transit, CGM sensor seal is broken. Please refund immediately!')" 
                    class="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 whitespace-nowrap">
                    📦 High-Value ($145) Claim ➔ Requires Manager Gate
                </button>
                <button onclick="pickPrompt('I signed up for SUB-3312 two days ago but my doctor is unavailable. Please cancel and refund $49.')" 
                    class="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 whitespace-nowrap">
                    ⚡ Auto-Approve SaaS (< $50)
                </button>
                <button onclick="pickPrompt('I want to return ORD-7740 blood pressure monitor purchased 2 months ago.')" 
                    class="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 whitespace-nowrap">
                    ⛔ Expired 60-Day Policy Return
                </button>
            </div>

            <div id="chatFeed" class="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
                <div class="flex items-start space-x-3 text-sm">
                    <div class="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold flex-shrink-0">
                        <i class="fa-solid fa-headset"></i>
                    </div>
                    <div class="bg-slate-100 p-3.5 rounded-xl rounded-tl-none max-w-xl text-slate-700">
                        Hello! I am your Autonomous Customer Support & Dispute Resolution Agent. Select a test dispute scenario above or describe your order issue.
                    </div>
                </div>
            </div>

            <div id="managerGate" class="hidden mx-4 mb-2 p-3 bg-amber-50 border border-amber-300 rounded-xl flex items-center justify-between text-xs">
                <div class="flex items-center space-x-2 text-amber-900">
                    <i class="fa-solid fa-shield-halved text-amber-600 text-lg"></i>
                    <div>
                        <span class="font-bold">Human Manager Authorization Required:</span>
                        <div id="gateReason" class="text-slate-700 text-[11px]">Reason pending</div>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <button onclick="handleManagerAction(true)" class="px-3 py-1.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 shadow-sm transition">
                        <i class="fa-solid fa-check mr-1"></i> Authorize $145 Refund
                    </button>
                    <button onclick="handleManagerAction(false)" class="px-3 py-1.5 bg-rose-600 text-white rounded-lg font-medium hover:bg-rose-700 shadow-sm transition">
                        <i class="fa-solid fa-ban mr-1"></i> Deny Claim
                    </button>
                </div>
            </div>

            <div class="p-3 border-t border-slate-200 bg-white flex items-center space-x-2 flex-shrink-0">
                <input id="chatInput" type="text" placeholder="Type your order claim or dispute..." 
                    class="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    onkeypress="if(event.key === 'Enter') submitChat()">
                <button onclick="submitChat()" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg text-sm flex items-center space-x-1.5 transition">
                    <span>Submit</span>
                    <i class="fa-solid fa-paper-plane text-xs"></i>
                </button>
            </div>
        </main>
    </div>

    <script>
        let activeSessionId = null;

        const orderInfo = {
            "ORD-9921": "<b>Customer:</b> Sarah Jenkins<br><b>Item:</b> Continuous Glucose Monitor (Pack of 2) - $145.00<br><b>Delivered:</b> 8 days ago (Within 30-day window)<br><b>Policy:</b> Over $50.00 requires Manager Gate",
            "SUB-3312": "<b>Customer:</b> Elena Rostova<br><b>Item:</b> Telehealth Concierge SaaS - $49.00<br><b>Billed:</b> 2 days ago (Within 7-day SaaS window)<br><b>Policy:</b> Under $50.00 Auto-Refunds instantly",
            "ORD-7740": "<b>Customer:</b> Marcus Vance<br><b>Item:</b> Smart Blood Pressure Monitor - $89.99<br><b>Delivered:</b> 60 days ago<br><b>Policy:</b> EXPIRED (Outside 30-day limit, 3 prior disputes)"
        };

        function updateOrderPreview() {
            const sel = document.getElementById('orderSelect').value;
            document.getElementById('orderPreviewBox').innerHTML = orderInfo[sel] || '';
        }

        function pickPrompt(text) {
            document.getElementById('chatInput').value = text;
        }

        async function submitChat() {
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if (!text) return;

            const orderId = document.getElementById('orderSelect').value;
            input.value = '';
            document.getElementById('managerGate').classList.add('hidden');

            appendMsg('customer', text);

            try {
                const res = await fetch('/api/v1/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: text, order_id: orderId, session_id: activeSessionId })
                });
                const data = await res.json();
                activeSessionId = data.session_id;

                appendMsg('agent', data.final_response, data.guardrail_flags, data.refund_transaction);

                if (data.needs_human_approval) {
                    document.getElementById('gateReason').innerText = data.human_approval_reason;
                    document.getElementById('managerGate').classList.remove('hidden');
                }
                updateStats();
            } catch (err) {
                console.error(err);
            }
        }

        function appendMsg(sender, text, guardrails, tx) {
            const feed = document.getElementById('chatFeed');
            if (sender === 'customer') {
                feed.innerHTML += `
                    <div class="flex items-start justify-end space-x-2 text-sm">
                        <div class="bg-indigo-600 text-white p-3 rounded-xl rounded-tr-none max-w-lg shadow-sm">
                            ${escapeHtml(text)}
                        </div>
                    </div>
                `;
            } else {
                let badges = '';
                if (guardrails) {
                    guardrails.forEach(g => {
                        badges += `<span class="px-2 py-0.5 rounded text-[10px] font-semibold ${g.passed ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'} mr-1">${g.guardrail}: ${g.passed ? 'PASS' : 'FLAGGED'}</span>`;
                    });
                }
                feed.innerHTML += `
                    <div class="flex items-start space-x-3 text-sm">
                        <div class="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold flex-shrink-0">
                            <i class="fa-solid fa-headset"></i>
                        </div>
                        <div class="bg-slate-100 border border-slate-200 p-3.5 rounded-xl rounded-tl-none max-w-2xl text-slate-800 space-y-2">
                            <div class="pb-1 border-b border-slate-200 flex items-center">${badges}</div>
                            <div class="whitespace-pre-wrap">${escapeHtml(text)}</div>
                        </div>
                    </div>
                `;
            }
            feed.scrollTop = feed.scrollHeight;
        }

        async function handleManagerAction(approved) {
            if (!activeSessionId) return;
            const res = await fetch('/api/v1/human-approval', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    session_id: activeSessionId,
                    approved: approved,
                    manager_notes: approved ? "Support Director approved exception for defective medical hardware." : "Rejected per non-returnable policy."
                })
            });
            const data = await res.json();
            document.getElementById('managerGate').classList.add('hidden');
            
            appendMsg('agent', data.updated_response, null, null);
        }

        async function updateStats() {
            try {
                const res = await fetch('/api/v1/telemetry');
                const data = await res.json();
                document.getElementById('tokensNum').innerText = data.total_tokens.toLocaleString();
                document.getElementById('costNum').innerText = '$' + data.total_cost_usd.toFixed(4);
            } catch(e){}
        }

        function escapeHtml(t) {
            return t ? t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : '';
        }
    </script>
</body>
</html>"""
