#!/usr/bin/env python
"""
Celery worker entry point for Broker Copilot.

To start the worker:
    celery -A celery_worker worker --loglevel=info

To start the beat scheduler (for periodic tasks):
    celery -A celery_worker beat --loglevel=info

To start both in one process (development only):
    celery -A celery_worker worker --beat --loglevel=info
"""

from app.email.celery_config import celery_app

# Import tasks to ensure they're registered
from app.email import tasks  # noqa: F401

if __name__ == "__main__":
    celery_app.start()
