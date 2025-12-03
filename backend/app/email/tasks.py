"""
Celery tasks for email scheduling and processing.

These tasks run in the background and handle:
- Processing pending scheduled emails
- Sending individual emails
- Bulk email campaigns
- Automatic renewal reminders
- Cleanup of old records
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from ..core.logging import get_logger
from .celery_config import celery_app
from .models import (
    ScheduledEmail, 
    EmailStatus, 
    EmailPriority, 
    RecurrenceType,
    EmailRecipient,
)
from .store import get_email_store
from .service import get_email_service, EmailProviderError

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="app.email.tasks.send_email",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(EmailProviderError,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_email(self, email_id: str, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a single scheduled email.
    
    This task is idempotent - it checks the email status before sending.
    
    Args:
        email_id: The ID of the scheduled email to send
        provider: Optional specific provider to use
        
    Returns:
        Dict with status and details
    """
    import asyncio
    
    task_id = self.request.id
    logger.info(
        "Starting send_email task",
        extra={
            "email_id": email_id,
            "task_id": task_id,
            "provider": provider,
            "retry_count": self.request.retries,
        }
    )
    
    async def _send():
        store = get_email_store()
        service = get_email_service()
        
        # Get the email
        logger.debug(f"Fetching email {email_id} from store")
        email = await store.get_email(email_id)
        if not email:
            logger.warning(f"Email {email_id} not found in store")
            return {"status": "error", "message": f"Email {email_id} not found"}
        
        logger.debug(
            "Email retrieved",
            extra={
                "email_id": email_id,
                "status": email.status.value,
                "subject": email.subject,
                "recipient_count": len(email.recipients),
            }
        )
        
        # Check if already sent or cancelled
        if email.status in (EmailStatus.SENT, EmailStatus.CANCELLED):
            logger.info(f"Email {email_id} already {email.status.value}, skipping")
            return {
                "status": "skipped", 
                "message": f"Email already {email.status.value}"
            }
        
        # Update status to sending
        logger.debug(f"Updating email {email_id} status to SENDING")
        await store.update_email_status(email_id, EmailStatus.SENDING)
        
        try:
            # Send the email
            logger.info(
                f"Sending email {email_id}",
                extra={
                    "subject": email.subject,
                    "recipients": [r.email for r in email.recipients[:5]],  # Limit for logging
                    "provider": provider,
                }
            )
            result = await service.send_email(email, provider_name=provider)
            
            # Update status to sent
            await store.update_email_status(
                email_id, 
                EmailStatus.SENT,
                message_id=result.get("message_id")
            )
            
            logger.info(
                f"Email {email_id} sent successfully",
                extra={
                    "provider": result.get("provider"),
                    "message_id": result.get("message_id"),
                    "task_id": task_id,
                }
            )
            
            # Handle recurrence
            if email.recurrence != RecurrenceType.NONE:
                logger.debug(f"Scheduling next recurrence for email {email_id}")
                await _schedule_next_recurrence(email)
            
            return {
                "status": "sent",
                "email_id": email_id,
                "provider": result.get("provider"),
                "message_id": result.get("message_id"),
            }
            
        except EmailProviderError as e:
            # Update status with error
            new_status = EmailStatus.PENDING if email.retry_count < email.max_retries else EmailStatus.FAILED
            await store.update_email_status(
                email_id,
                new_status,
                error_message=str(e)
            )
            
            logger.warning(
                f"Email {email_id} send failed",
                extra={
                    "error": str(e),
                    "retry_count": email.retry_count,
                    "max_retries": email.max_retries,
                    "new_status": new_status.value,
                    "task_id": task_id,
                }
            )
            
            # Re-raise for Celery retry
            if email.retry_count < email.max_retries:
                raise
            
            logger.error(
                f"Email {email_id} failed permanently after {email.retry_count} retries",
                extra={"error": str(e)}
            )
            
            return {
                "status": "failed",
                "email_id": email_id,
                "error": str(e),
                "retries": email.retry_count,
            }
        except Exception as e:
            logger.exception(
                f"Unexpected error sending email {email_id}",
                extra={"error": str(e), "task_id": task_id}
            )
            raise
    
    # Run async function in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send())
    except Exception as e:
        logger.exception(f"Task send_email failed for {email_id}")
        raise
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.email.tasks.send_email_urgent",
    max_retries=5,
    default_retry_delay=30,
)
def send_email_urgent(self, email_id: str) -> Dict[str, Any]:
    """
    Send an urgent email with higher retry priority.
    
    Uses the priority queue for faster processing.
    """
    logger.info(
        f"Processing urgent email {email_id}",
        extra={
            "task_id": self.request.id,
            "retry_count": self.request.retries,
        }
    )
    return send_email(email_id)


@celery_app.task(name="app.email.tasks.process_pending_emails")
def process_pending_emails() -> Dict[str, Any]:
    """
    Process all pending emails that are due to be sent.
    
    This task runs periodically (every 30 seconds) and queues
    individual send tasks for each pending email.
    """
    import asyncio
    
    logger.info("Starting process_pending_emails task")
    
    async def _process():
        store = get_email_store()
        now = datetime.utcnow()
        
        # Get pending emails due to be sent
        logger.debug(f"Fetching pending emails before {now}")
        pending = await store.get_pending_emails(before=now, limit=100)
        
        if not pending:
            logger.debug("No pending emails to process")
            return {"status": "ok", "processed": 0}
        
        logger.info(f"Found {len(pending)} pending emails to process")
        
        queued = 0
        urgent_count = 0
        normal_count = 0
        
        for email in pending:
            try:
                # Queue the email for sending based on priority
                if email.priority in (EmailPriority.URGENT, EmailPriority.HIGH):
                    send_email_urgent.delay(email.id)
                    urgent_count += 1
                else:
                    send_email.delay(email.id)
                    normal_count += 1
                
                # Mark as queued
                await store.update_email_status(email.id, EmailStatus.QUEUED)
                queued += 1
            except Exception as e:
                logger.error(
                    f"Failed to queue email {email.id}",
                    extra={"error": str(e)}
                )
        
        logger.info(
            f"Queued {queued} pending emails",
            extra={
                "total": len(pending),
                "queued": queued,
                "urgent": urgent_count,
                "normal": normal_count,
            }
        )
        return {"status": "ok", "processed": queued, "urgent": urgent_count, "normal": normal_count}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process())
    except Exception as e:
        logger.exception("Error in process_pending_emails task")
        return {"status": "error", "error": str(e)}
    finally:
        loop.close()


@celery_app.task(name="app.email.tasks.send_bulk_emails")
def send_bulk_emails(
    email_ids: List[str],
    batch_size: int = 10,
    delay_between_batches: float = 1.0,
) -> Dict[str, Any]:
    """
    Send a batch of emails with rate limiting.
    
    Args:
        email_ids: List of email IDs to send
        batch_size: Number of emails per batch
        delay_between_batches: Seconds to wait between batches
    """
    import asyncio
    import time
    
    logger.info(
        "Starting bulk email send",
        extra={
            "total_emails": len(email_ids),
            "batch_size": batch_size,
            "delay_between_batches": delay_between_batches,
        }
    )
    
    results = {
        "total": len(email_ids),
        "sent": 0,
        "failed": 0,
        "skipped": 0,
    }
    
    # Process in batches
    batch_number = 0
    for i in range(0, len(email_ids), batch_size):
        batch = email_ids[i:i + batch_size]
        batch_number += 1
        
        logger.debug(
            f"Processing batch {batch_number}",
            extra={
                "batch_start": i,
                "batch_size": len(batch),
            }
        )
        
        # Queue each email in the batch
        for email_id in batch:
            try:
                result = send_email(email_id)
                if result.get("status") == "sent":
                    results["sent"] += 1
                elif result.get("status") == "skipped":
                    results["skipped"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                logger.error(
                    f"Bulk email {email_id} failed",
                    extra={
                        "error": str(e),
                        "batch_number": batch_number,
                    }
                )
                results["failed"] += 1
        
        # Rate limiting between batches
        if i + batch_size < len(email_ids):
            logger.debug(f"Rate limiting: sleeping {delay_between_batches}s between batches")
            time.sleep(delay_between_batches)
    
    logger.info(
        "Bulk email send complete",
        extra={
            "total": results["total"],
            "sent": results["sent"],
            "failed": results["failed"],
            "skipped": results["skipped"],
            "batches": batch_number,
        }
    )
    return results


@celery_app.task(name="app.email.tasks.send_renewal_reminders")
def send_renewal_reminders() -> Dict[str, Any]:
    """
    Automatically send renewal reminder emails based on policy expiration dates.
    
    This task runs hourly and checks for policies that need reminders.
    """
    import asyncio
    
    logger.info("Starting renewal reminders check")
    
    async def _check_renewals():
        store = get_email_store()
        
        # This would typically query a database or CRM for policies
        logger.debug("Querying for policies requiring renewal reminders")
        
        # In production, this would:
        # 1. Query policies expiring in 30, 14, 7 days
        # 2. Check if reminder already sent
        # 3. Create and queue reminder emails
        
        logger.info("Renewal reminder check completed")
        return {"status": "ok", "checked": True}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check_renewals())
    except Exception as e:
        logger.exception("Error checking renewal reminders")
        return {"status": "error", "error": str(e)}
    finally:
        loop.close()


@celery_app.task(name="app.email.tasks.cleanup_old_emails")
def cleanup_old_emails(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old sent/failed email records.
    
    Args:
        days_to_keep: Number of days to keep email records
    """
    import asyncio
    
    logger.info(
        "Starting email cleanup task",
        extra={"days_to_keep": days_to_keep}
    )
    
    async def _cleanup():
        store = get_email_store()
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        
        logger.debug(f"Cleaning up emails older than {cutoff}")
        
        deleted = 0
        checked = 0
        # Get all emails and filter old ones
        for email_id, email in list(store._emails.items()):
            checked += 1
            if email.status in (EmailStatus.SENT, EmailStatus.FAILED, EmailStatus.CANCELLED):
                if email.updated_at < cutoff:
                    await store.delete_email(email_id)
                    deleted += 1
                    logger.debug(f"Deleted old email {email_id} with status {email.status.value}")
        
        logger.info(
            "Email cleanup completed",
            extra={
                "checked": checked,
                "deleted": deleted,
                "cutoff_date": cutoff.isoformat(),
            }
        )
        return {"status": "ok", "deleted": deleted, "checked": checked}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_cleanup())
    except Exception as e:
        logger.exception("Error in email cleanup task")
        return {"status": "error", "error": str(e)}
    finally:
        loop.close()


async def _schedule_next_recurrence(email: ScheduledEmail):
    """
    Schedule the next occurrence of a recurring email.
    """
    store = get_email_store()
    
    logger.debug(
        f"Calculating next recurrence for email {email.id}",
        extra={
            "recurrence_type": email.recurrence.value,
            "current_scheduled_at": email.scheduled_at.isoformat(),
        }
    )
    
    # Calculate next scheduled time
    if email.recurrence == RecurrenceType.DAILY:
        next_time = email.scheduled_at + timedelta(days=1)
    elif email.recurrence == RecurrenceType.WEEKLY:
        next_time = email.scheduled_at + timedelta(weeks=1)
    elif email.recurrence == RecurrenceType.MONTHLY:
        # Add approximately one month
        next_time = email.scheduled_at + timedelta(days=30)
    else:
        logger.debug(f"No recurrence scheduled for email {email.id} (type: {email.recurrence})")
        return  # No recurrence or unsupported type
    
    # Check if we should create another occurrence
    if email.recurrence_end and next_time > email.recurrence_end:
        logger.info(
            f"Recurrence ended for email {email.id}",
            extra={
                "next_time": next_time.isoformat(),
                "recurrence_end": email.recurrence_end.isoformat(),
            }
        )
        return
    if email.recurrence_count is not None and email.recurrence_count <= 0:
        logger.info(f"Recurrence count exhausted for email {email.id}")
        return
    
    # Create new email for next occurrence
    new_email = ScheduledEmail(
        subject=email.subject,
        body_html=email.body_html,
        body_text=email.body_text,
        template_id=email.template_id,
        template_variables=email.template_variables,
        from_email=email.from_email,
        from_name=email.from_name,
        recipients=email.recipients,
        reply_to=email.reply_to,
        attachments=email.attachments,
        scheduled_at=next_time,
        timezone=email.timezone,
        recurrence=email.recurrence,
        recurrence_end=email.recurrence_end,
        recurrence_count=email.recurrence_count - 1 if email.recurrence_count else None,
        priority=email.priority,
        policy_id=email.policy_id,
        user_id=email.user_id,
        campaign_id=email.campaign_id,
        tags=email.tags,
    )
    
    await store.save_email(new_email)
    logger.info(
        f"Scheduled next recurrence",
        extra={
            "original_email_id": email.id,
            "new_email_id": new_email.id,
            "scheduled_at": next_time.isoformat(),
            "remaining_count": email.recurrence_count - 1 if email.recurrence_count else None,
        }
    )


# ============================================================================
# Helper functions for scheduling from the API
# ============================================================================

def schedule_email_task(
    email_id: str,
    scheduled_at: datetime,
    priority: EmailPriority = EmailPriority.NORMAL,
) -> str:
    """
    Schedule an email to be sent at a specific time.
    
    Returns the Celery task ID.
    """
    logger.info(
        "Scheduling email task",
        extra={
            "email_id": email_id,
            "scheduled_at": scheduled_at.isoformat(),
            "priority": priority.value,
        }
    )
    
    # Calculate ETA
    eta = scheduled_at
    
    # Choose task based on priority
    if priority in (EmailPriority.URGENT, EmailPriority.HIGH):
        task = send_email_urgent
        logger.debug(f"Using urgent queue for email {email_id}")
    else:
        task = send_email
        logger.debug(f"Using normal queue for email {email_id}")
    
    # Schedule the task
    result = task.apply_async(
        args=[email_id],
        eta=eta,
        priority=0 if priority == EmailPriority.URGENT else 5,
    )
    
    logger.info(
        f"Email task scheduled successfully",
        extra={
            "email_id": email_id,
            "task_id": result.id,
            "eta": eta.isoformat(),
        }
    )
    
    return result.id


def cancel_email_task(task_id: str) -> bool:
    """
    Cancel a scheduled email task.
    
    Returns True if successfully cancelled.
    """
    from celery.result import AsyncResult
    
    logger.info(f"Cancelling email task", extra={"task_id": task_id})
    
    try:
        result = AsyncResult(task_id, app=celery_app)
        result.revoke(terminate=True)
        logger.info(f"Email task cancelled successfully", extra={"task_id": task_id})
        return True
    except Exception as e:
        logger.error(
            f"Failed to cancel email task",
            extra={"task_id": task_id, "error": str(e)}
        )
        raise
