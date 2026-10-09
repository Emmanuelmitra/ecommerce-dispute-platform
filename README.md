# Clinical E-Commerce & SaaS AI Dispute & Auto-Refund Platform

An enterprise-grade, multi-agent AI customer support platform built on the **Google Agent Development Kit (Google ADK / GenAI)** architecture.

Automates e-commerce return verifications, pro-rated SaaS cancellations, and instant financial refunds while enforcing fraud prevention limits, sterile medical item policies, and human manager approval gates.

---

## 🌟 Architecture & Multi-Agent Pipeline

```
Customer Dispute Query (e.g. damaged package, cancellation, refund request)
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│ 1. PRIVACY & SECURITY GUARDRAILS                       │
│  • PIIScrubber (Masks customer cards, SSNs, phones)    │
│  • PromptGuard (Blocks social engineering/jailbreaks)  │
└──────────────────────┬─────────────────────────────────┘
                       │ Sanitized Query
                       ▼
┌────────────────────────────────────────────────────────┐
│ 2. TRIAGE & SENTIMENT AGENT                            │
│  • Analyzes sentiment, urgency & extracts Order IDs    │
│  • Queries Order Repository DB (ORD-9921, SUB-3312)    │
└──────────────────────┬─────────────────────────────────┘
                       │ Order History & Tracking Details
                       ▼
┌────────────────────────────────────────────────────────┐
│ 3. ENTERPRISE POLICY AUDIT AGENT                       │
│  • Evaluates 30-day return window & item hygiene seals │
│  • Checks customer dispute history & risk scores       │
│  • Evaluates Autonomous Settlement Cap ($50.00)        │
└──────────────────────┬─────────────────────────────────┘
                       │ Decision Branch
         ┌─────────────┴─────────────┐
         ▼                           ▼
[Within Policy & ≤ $50]     [High Value > $50 OR Flagged]
         │                           │
┌─────────────────────────┐ ┌──────────────────────────────────────┐
│ 4. AUTO-SETTLEMENT      │ │ 4. HUMAN MANAGER APPROVAL GATE       │
│  • Executes Gateway Tx  │ │  • Pauses autonomous execution       │
│  • Generates Refund ID  │ │  • Generates Manager Decision Card   │
└────────┬────────────────┘ └──────────────────┬───────────────────┘
         │                                     │ Manager Authorizes
         │                                     ▼
         └───────────────────────► ┌───────────────────────────────┐
                                   │ 5. CUSTOMER OUTREACH AGENT    │
                                   │  • Issues formal email notice │
                                   │  • Cites transaction/timeline │
                                   └───────────────────────────────┘
```

---

## 🚀 Quickstart

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the automated test suite
python3 -m unittest discover -s tests -p "test_*.py"

# 4. Launch the application
uvicorn src.main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) to access the interactive web interface.

---

## ☁️ Cloud Deployment (Google Cloud Run)

```bash
gcloud run deploy ecommerce-dispute-platform \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8000
```
