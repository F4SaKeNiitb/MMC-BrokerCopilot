#!/usr/bin/env bash
# Simple run script for development
set -e
source .venv/bin/activate || true
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
