# Broker Copilot

AI-augmented workflow platform for insurance brokers. Built with a **Zero-Storage, Connector-Driven Architecture**.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│   Dashboard │ Brief Viewer │ Chat │ Template Editor              │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST/Streaming
┌─────────────────────────────▼───────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Connectors  │  │  Gemini LLM │  │   Scoring Engine        │  │
│  │ (Graph/CRM) │  │  Function   │  │   (Deterministic +      │  │
│  │             │  │  Calling    │  │    AI Explanation)      │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                     │                 │
│         └────────────────┴─────────────────────┘                 │
│                          │                                       │
│              Provenance Injection Layer                          │
│              (Citation tracking & deep links)                    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ OAuth 2.0
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Microsoft 365 │    │     CRM       │    │    Teams      │
│ (Graph API)   │    │  (Salesforce) │    │   (Chat)      │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Core Principles

### Zero-Storage Policy
- **No persistent database** for client/policy data
- **No vector databases** or document storage
- All business data fetched live, processed in ephemeral memory, discarded after request

### Glass-Box Transparency
- Every AI insight includes **Data Provenance**
- Clickable **Source Links** for every fact
- Deep links to original records (Outlook, CRM, etc.)

### Connector-Driven
- Read-only APIs with OAuth 2.0 delegated permissions
- System acts as an overlay, not a data store

## Features

### 1. Live Connector Layer
- OAuth 2.0 token management (access/refresh lifecycle)
- Minimalist fetching (metadata + snippets only)
- Concurrent aggregation (<3s response goal)
- Graceful fallback on API failures

### 2. Intelligent Renewal Dashboard
- Live pipeline visualization (Kanban/list)
- Advanced filtering (30/60/90 days, policy type, assignee)
- Hybrid prioritization:
  - **Layer 1**: Deterministic scoring (premium, time decay, claims)
  - **Layer 2**: LLM-generated explanation

### 3. One-Page Briefs
- Multi-source synthesis (CRM, Email, Calendar, Teams)
- Structured AI output with citations
- Streaming responses for low latency

### 4. Template-Based Outreach
- Jinja2 + Markdown templates
- Live variable resolution
- Multi-channel delivery options

### 5. Connector-Backed Q&A (Chat)
- Gemini function-calling for multi-hop reasoning
- Hallucination guardrails
- Confidence scoring

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/aggregate` | POST | Aggregate snippets from connectors |
| `/score/{policy_id}` | GET | Get deterministic priority score |
| `/brief/{policy_id}` | GET | Generate one-page brief (streaming) |
| `/chat` | POST | Q&A with function-calling |
| `/chat/stream` | POST | Streaming chat responses |
| `/renewals` | POST | Get filtered renewal pipeline |
| `/renewals/override` | POST | Manual priority override |
| `/render-template` | POST | Render Jinja2 template |
| `/oauth/start` | GET | Start OAuth flow |
| `/oauth/callback` | GET | OAuth callback handler |

## Quick Start

### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Gemini API key and OAuth credentials

# Run server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Get priority score
curl http://localhost:8000/score/POL-123

# Generate brief (streaming)
curl http://localhost:8000/brief/POL-123

# Chat query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "Who is the underwriter for POL-123?"}'

# Get renewals pipeline
curl -X POST http://localhost:8000/renewals \
  -H "Content-Type: application/json" \
  -d '{"days_window": 90, "sort_by": "score"}'
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required for LLM |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `USE_LLM` | Enable/disable LLM features | `true` |
| `AZURE_CLIENT_ID` | Microsoft OAuth client ID | - |
| `AZURE_CLIENT_SECRET` | Microsoft OAuth secret | - |
| `AZURE_TENANT` | Azure AD tenant | `common` |

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & endpoints
│   ├── priority.py          # Deterministic scoring engine
│   ├── brief.py             # Brief generation with LLM
│   ├── chat_agent.py        # Q&A with function-calling
│   ├── templates.py         # Jinja2 template engine
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py          # Connector interface
│   │   └── microsoft_graph.py
│   └── llm/
│       ├── __init__.py
│       ├── gemini.py        # Gemini client & function-calling
│       └── provenance.py    # Citation injection
├── requirements.txt
├── .env.example
└── README.md
```

## TODO (Production Readiness)

- [ ] Implement real Microsoft Graph OAuth token exchange
- [ ] Add CRM connector (Salesforce/HubSpot)
- [ ] Secure token vault (Azure Key Vault / AWS Secrets Manager)
- [ ] Rate limiting and request throttling
- [ ] Comprehensive error handling and logging
- [ ] Unit and integration tests
- [ ] Frontend implementation (Next.js)
- [ ] PDF generation for briefs
- [ ] Email scheduling (background task queue)

## License

Proprietary - All rights reserved
