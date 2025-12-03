Broker Copilot - Backend (FastAPI)

Overview
- FastAPI backend scaffolding for Broker Copilot.
- Zero-Storage policy: no persistent database; tokens and state are ephemeral in memory.

Run (local, dev):

1) Create virtualenv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Copy `.env.example` -> `.env` and fill OAuth/Gemini values.

3) Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Notes & TODOs
- This is a scaffold demonstrating connector-driven, zero-storage architecture.
- `#TODO` markers indicate production work (secure token store, proper OAuth client registration, actual Gemini integration).
