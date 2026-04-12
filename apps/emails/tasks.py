"""
apps/emails/tasks.py
---------------------
Celery tasks for all Rendi email triggers.

In development: tasks run synchronously (CELERY_TASK_ALWAYS_EAGER=True).
In production: tasks run async via Redis broker.

Each task is designed to be safe to retry — all sending logic is
idempotent (duplicate checks live in service.py).
"""

import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


# ------------------------------------------------------------------
# Triggered immediately after events
# ------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email_task(self, user_id: int):
    """Trigger: user_signed_up"""
    try:
        from apps.emails.service import send_welcome_email
        user = User.objects.get(pk=user_id)
        send_welcome_email(user)
    except User.DoesNotExist:
        logger.warning("send_welcome_email_task: user %s not found", user_id)
    except Exception as exc:
        logger.error("send_welcome_email_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_results_email_task(self, user_id: int, assessment_id: int):
    """Trigger: assessment_completed"""
    try:
        from apps.emails.service import send_results_email
        from apps.assessments.models import Assessment
        user = User.objects.get(pk=user_id)
        assessment = Assessment.objects.get(pk=assessment_id)
        send_results_email(user, assessment)
    except (User.DoesNotExist, Exception) as exc:
        logger.error("send_results_email_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_progress_email_task(self, user_id: int, assessment_id: int, previous_score: int):
    """Trigger: assessment_updated with score improvement"""
    try:
        from apps.emails.service import send_progress_email
        from apps.assessments.models import Assessment
        user = User.objects.get(pk=user_id)
        assessment = Assessment.objects.get(pk=assessment_id)
        send_progress_email(user, assessment, previous_score)
    except Exception as exc:
        logger.error("send_progress_email_task failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_post_assessment_emails_task(self, user_id: int, assessment_id: int):
    """
    Runs immediately after assessment submission.
    Sends contextual emails based on the result:
      - Results email (always)
      - Deposit blocker email (if deposit is biggest blocker)
      - Fastest improvement email (if simulations show meaningful gain)
      - Near ready email (if score is Getting close / Strong position)
      - Advisor ready email (if all thresholds met)
    """
    try:
        from apps.emails.service import (
            send_results_email,
            send_deposit_blocker_email,
            send_fastest_improvement_email,
            send_near_ready_email,
            send_advisor_ready_email,
        )
        from apps.assessments.models import Assessment

        user = User.objects.get(pk=user_id)
        assessment = Assessment.objects.get(pk=assessment_id)

        send_results_email(user, assessment)
        send_deposit_blocker_email(user, assessment)
        send_fastest_improvement_email(user, assessment)
        send_near_ready_email(user, assessment)
        send_advisor_ready_email(user, assessment)

    except Exception as exc:
        logger.error("send_post_assessment_emails_task failed: %s", exc)
        raise self.retry(exc=exc)


# ------------------------------------------------------------------
# Scheduled tasks (run via Celery Beat — set up in production)
# ------------------------------------------------------------------

@shared_task
def send_inactivity_reminders_task():
    """
    Checks all users and sends reminder emails based on inactivity.
    Should be scheduled to run daily via Celery Beat.

    Logic:
      - 7 days since last assessment and no 7-day reminder sent
      - 14 days since last assessment and no 14-day reminder sent
      - 30 days since last assessment and no 30-day reminder sent
    """
    from apps.emails.service import (
        send_reminder_7_email,
        send_reminder_14_email,
        send_reengagement_email,
    )
    from apps.assessments.models import Assessment

    now = timezone.now()
    sent_count = 0

    # Get all users who have at least one assessment
    user_ids = Assessment.objects.values_list("user_id", flat=True).distinct()
    users = User.objects.filter(pk__in=user_ids)

    for user in users:
        latest = (
            Assessment.objects.filter(user=user)
            .order_by("-created_at")
            .first()
        )
        if not latest:
            continue

        days_inactive = (now - latest.created_at).days

        if days_inactive >= 30:
            if send_reengagement_email(user):
                sent_count += 1
        elif days_inactive >= 14:
            if send_reminder_14_email(user):
                sent_count += 1
        elif days_inactive >= 7:
            if send_reminder_7_email(user):
                sent_count += 1

    logger.info("send_inactivity_reminders_task: sent %d emails", sent_count)
    return sent_count


@shared_task
def send_advisor_followup_task():
    """
    Checks for users who received an advisor_ready email 7+ days ago
    but haven't received a follow-up yet.
    Should be scheduled to run daily via Celery Beat.
    """
    from apps.emails.service import send_advisor_followup_email
    from apps.emails.models import EmailLog
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=7)
    advisor_ready_logs = EmailLog.objects.filter(
        email_type=EmailLog.ADVISOR_READY,
        success=True,
        sent_at__lte=cutoff,
    ).select_related("user")

    sent_count = 0
    for log in advisor_ready_logs:
        if send_advisor_followup_email(log.user):
            sent_count += 1

    logger.info("send_advisor_followup_task: sent %d emails", sent_count)
    return sent_count
