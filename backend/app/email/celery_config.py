"""
Celery configuration for background task processing.

Uses Redis as the message broker for reliable task queuing.
"""

import os
from celery import Celery
from kombu import Queue, Exchange
from datetime import timedelta

# Redis configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Create Celery app
celery_app = Celery(
    "broker_copilot",
    broker=REDIS_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.email.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Retry if worker dies
    worker_prefetch_multiplier=1,  # One task at a time per worker
    
    # Result backend settings
    result_expires=timedelta(days=7),
    result_extended=True,  # Include task name in result
    
    # Task time limits (seconds)
    task_soft_time_limit=300,  # 5 min soft limit
    task_time_limit=600,  # 10 min hard limit
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute default retry delay
    task_max_retries=3,
    
    # Beat scheduler settings (for periodic tasks)
    beat_scheduler="celery.beat:PersistentScheduler",
    beat_schedule_filename="celerybeat-schedule",
    
    # Scheduled tasks (beat schedule)
    beat_schedule={
        "process-pending-emails": {
            "task": "app.email.tasks.process_pending_emails",
            "schedule": timedelta(seconds=30),  # Check every 30 seconds
            "options": {"queue": "email_scheduler"}
        },
        "cleanup-old-emails": {
            "task": "app.email.tasks.cleanup_old_emails",
            "schedule": timedelta(hours=24),  # Daily cleanup
            "options": {"queue": "maintenance"}
        },
        "send-renewal-reminders": {
            "task": "app.email.tasks.send_renewal_reminders",
            "schedule": timedelta(hours=1),  # Hourly check for reminders
            "options": {"queue": "email_priority"}
        },
    },
    
    # Queue routing
    task_routes={
        "app.email.tasks.send_email": {"queue": "email_default"},
        "app.email.tasks.send_email_urgent": {"queue": "email_priority"},
        "app.email.tasks.process_pending_emails": {"queue": "email_scheduler"},
        "app.email.tasks.cleanup_old_emails": {"queue": "maintenance"},
        "app.email.tasks.send_renewal_reminders": {"queue": "email_priority"},
        "app.email.tasks.send_bulk_emails": {"queue": "email_bulk"},
    },
)

# Define queues with priorities
celery_app.conf.task_queues = (
    Queue("email_priority", Exchange("email_priority"), routing_key="email.priority",
          queue_arguments={"x-max-priority": 10}),
    Queue("email_default", Exchange("email_default"), routing_key="email.default"),
    Queue("email_bulk", Exchange("email_bulk"), routing_key="email.bulk"),
    Queue("email_scheduler", Exchange("email_scheduler"), routing_key="email.scheduler"),
    Queue("maintenance", Exchange("maintenance"), routing_key="maintenance"),
)

# Default queue
celery_app.conf.task_default_queue = "email_default"
celery_app.conf.task_default_exchange = "email_default"
celery_app.conf.task_default_routing_key = "email.default"


def get_celery_app() -> Celery:
    """Get the configured Celery app instance."""
    return celery_app
