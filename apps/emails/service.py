"""
apps/emails/service.py
-----------------------
Core email sending service for Rendi.

All 11 email types from the spec are implemented here as standalone
functions. Each function:
  1. Checks the EmailLog to prevent duplicate sends
  2. Builds the subject + plain-text body using exact copy from spec
  3. Sends via Django's email backend (console in dev, SendGrid in prod)
  4. Writes an EmailLog record (success or failure)

All monetary values passed in should be plain integers/floats (no £ symbol).
Formatting is applied inside each function.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailLog

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fmt_currency(value) -> str:
    """Format a number as £12,345 with no decimal places."""
    try:
        return f"£{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)


def _already_sent(user, email_type: str, within_days: int = None) -> bool:
    """
    Returns True if this email type was already sent to the user.
    If within_days is given, only checks within that window.
    """
    qs = EmailLog.objects.filter(user=user, email_type=email_type, success=True)
    if within_days:
        cutoff = timezone.now() - timedelta(days=within_days)
        qs = qs.filter(sent_at__gte=cutoff)
    return qs.exists()


def _send(user, email_type: str, subject: str, body: str, assessment=None) -> bool:
    """
    Low-level send helper. Logs success or failure to EmailLog.
    Returns True if the email was sent successfully.
    """
    from_email = getattr(settings, "EMAIL_FROM", settings.DEFAULT_FROM_EMAIL)
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=False,
        )
        EmailLog.objects.create(
            user=user,
            email_type=email_type,
            subject=subject,
            success=True,
            assessment=assessment,
        )
        logger.info("Email sent | type=%s | to=%s", email_type, user.email)
        return True
    except Exception as exc:
        EmailLog.objects.create(
            user=user,
            email_type=email_type,
            subject=subject,
            success=False,
            error=str(exc),
            assessment=assessment,
        )
        logger.error(
            "Email failed | type=%s | to=%s | error=%s",
            email_type, user.email, exc
        )
        return False


# ------------------------------------------------------------------
# 1. Welcome email  (Trigger: user_signed_up)
# ------------------------------------------------------------------

def send_welcome_email(user) -> bool:
    """Send once on registration. Never resend."""
    if _already_sent(user, EmailLog.WELCOME):
        return False

    subject = "You might be closer to buying a home than you think"
    body = f"""Hi {user.first_name or 'there'},

Welcome to Rendi.

Most people trying to buy their first home don't actually know how close they are — they're left guessing.

Rendi is here to change that.

In just a few minutes, you'll be able to:
- See how ready you are to buy
- Understand what's holding you back
- Get a clear path forward

Check your readiness now: {settings.FRONTEND_URL}/dashboard/assessment

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.WELCOME, subject, body)


# ------------------------------------------------------------------
# 2. Results email  (Trigger: assessment_completed)
# ------------------------------------------------------------------

def send_results_email(user, assessment) -> bool:
    """
    Send after every assessment submission.
    Uses personalised data: score, timeline, biggest blocker, recommendation.
    """
    subject = "Here's where you stand — and what's holding you back"

    biggest_blocker = assessment.biggest_blocker or "your deposit"
    blocker_label = {
        "deposit":     "your deposit",
        "income":      "your income-to-price ratio",
        "commitments": "your monthly commitments",
        "credit":      "your credit profile",
    }.get(biggest_blocker, biggest_blocker)

    # First non-revisit recommendation
    recommendations = assessment.recommendations or []
    primary_rec = next(
        (r for r in recommendations if not r.lower().startswith("you can revisit")),
        "Focus on the area with the biggest impact on your score."
    )

    body = f"""Hi {user.first_name or 'there'},

Your readiness score: {assessment.score}/100
Estimated timeline: {assessment.time_estimate}

Your biggest blocker:
Improving {blocker_label} will have the most impact on your score.

Next step:
{primary_rec}

View your full plan: {settings.FRONTEND_URL}/dashboard/result

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.RESULTS, subject, body, assessment=assessment)


# ------------------------------------------------------------------
# 3. 7-day reminder  (Trigger: user_inactive_7_days)
# ------------------------------------------------------------------

def send_reminder_7_email(user) -> bool:
    """Only send if not already sent within the last 7 days."""
    if _already_sent(user, EmailLog.REMINDER_7, within_days=7):
        return False

    subject = "You may already be closer than you were last week"
    body = f"""Hi {user.first_name or 'there'},

Your financial position may have improved.

Update your readiness and see where you stand now: {settings.FRONTEND_URL}/dashboard/assessment

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.REMINDER_7, subject, body)


# ------------------------------------------------------------------
# 4. 14-day reminder  (Trigger: user_inactive_14_days)
# ------------------------------------------------------------------

def send_reminder_14_email(user) -> bool:
    if _already_sent(user, EmailLog.REMINDER_14, within_days=14):
        return False

    subject = "Still planning to buy a home?"
    body = f"""Hi {user.first_name or 'there'},

Your readiness evolves over time.

Update your progress and see what's changed: {settings.FRONTEND_URL}/dashboard/assessment

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.REMINDER_14, subject, body)


# ------------------------------------------------------------------
# 5. Progress email  (Trigger: assessment_updated with score improvement)
# ------------------------------------------------------------------

def send_progress_email(user, assessment, previous_score: int) -> bool:
    score_delta = assessment.score - previous_score
    if score_delta <= 0:
        return False  # Only send on genuine improvement

    subject = "You're making real progress"
    body = f"""Hi {user.first_name or 'there'},

Your new score: {assessment.score}/100
Change: +{score_delta}

You're closer to your goal.

See your updated plan: {settings.FRONTEND_URL}/dashboard/result

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.PROGRESS, subject, body, assessment=assessment)


# ------------------------------------------------------------------
# 6. Deposit blocker email  (Trigger: deposit_is_biggest_blocker)
# ------------------------------------------------------------------

def send_deposit_blocker_email(user, assessment) -> bool:
    """Send when deposit is the identified biggest blocker."""
    if assessment.biggest_blocker != "deposit":
        return False
    if _already_sent(user, EmailLog.DEPOSIT_BLOCKER, within_days=30):
        return False

    deposit_gap = _fmt_currency(assessment.deposit_gap)

    # Pick the middle simulation scenario (£500/month) if available
    simulations = assessment.simulations or []
    mid_sim = next((s for s in simulations if s.get("monthly_saving") == 500), None)
    if mid_sim:
        monthly_saving = _fmt_currency(mid_sim["monthly_saving"])
        months_to_goal = mid_sim["months_to_goal"]
        sim_line = f"Saving {monthly_saving} per month could help you reach your goal in {months_to_goal} months."
    else:
        sim_line = "Building your deposit consistently each month will improve your position over time."

    subject = "This is the one thing holding you back most"
    body = f"""Hi {user.first_name or 'there'},

You need approximately {deposit_gap} more in savings to reach the 10% deposit benchmark.

{sim_line}

See your full savings plan: {settings.FRONTEND_URL}/dashboard/result

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.DEPOSIT_BLOCKER, subject, body, assessment=assessment)


# ------------------------------------------------------------------
# 7. Fastest improvement email  (Trigger: simulation_available)
# ------------------------------------------------------------------

def send_fastest_improvement_email(user, assessment) -> bool:
    """Send when simulations are available and show meaningful improvement."""
    simulations = assessment.simulations or []
    if not simulations:
        return False
    if _already_sent(user, EmailLog.FASTEST_IMPROVEMENT, within_days=30):
        return False

    # Use the highest saving scenario
    best_sim = max(simulations, key=lambda s: s.get("months_saved", 0))
    if best_sim.get("months_saved", 0) <= 0:
        return False

    scenario_saving = _fmt_currency(best_sim["monthly_saving"])

    subject = "This could get you there faster"
    body = f"""Hi {user.first_name or 'there'},

If you save {scenario_saving} per month, you could reduce your timeline significantly.

{best_sim.get('summary', '')}

Explore your updated plan: {settings.FRONTEND_URL}/dashboard/result

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(
        user, EmailLog.FASTEST_IMPROVEMENT, subject, body, assessment=assessment
    )


# ------------------------------------------------------------------
# 8. Near ready email  (Trigger: score crosses into "Getting close")
# ------------------------------------------------------------------

def send_near_ready_email(user, assessment) -> bool:
    if assessment.status not in ("Getting close", "Strong position"):
        return False
    if _already_sent(user, EmailLog.NEAR_READY, within_days=30):
        return False

    subject = "You're getting close"
    body = f"""Hi {user.first_name or 'there'},

You're getting close to being ready.

Update your progress to see how far you've come: {settings.FRONTEND_URL}/dashboard/result

Know someone planning to buy a home? Invite them to compare their readiness:
{settings.FRONTEND_URL}/register

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.NEAR_READY, subject, body, assessment=assessment)


# ------------------------------------------------------------------
# 9. Advisor ready email  (Trigger: user_advisor_ready)
#    Score >= 70, deposit gap minimal, timeline short
# ------------------------------------------------------------------

def send_advisor_ready_email(user, assessment) -> bool:
    is_ready = (
        assessment.score >= 70
        and float(assessment.deposit_gap) < float(assessment.deposit_needed) * 0.2
        and assessment.estimated_months <= 6
    )
    if not is_ready:
        return False
    if _already_sent(user, EmailLog.ADVISOR_READY, within_days=60):
        return False

    subject = "You may be ready to speak to a mortgage advisor"
    body = f"""Hi {user.first_name or 'there'},

You appear to be in a strong position to take the next step.

Your readiness score: {assessment.score}/100
Timeline: {assessment.time_estimate}

Speak to a mortgage advisor to understand your options: {settings.FRONTEND_URL}/dashboard

— Team Rendi

This is an estimate for information only. Not financial advice. A mortgage advisor can provide regulated advice tailored to your circumstances."""

    return _send(user, EmailLog.ADVISOR_READY, subject, body, assessment=assessment)


# ------------------------------------------------------------------
# 10. Advisor follow-up  (Trigger: advisor_ready_no_click after 7 days)
# ------------------------------------------------------------------

def send_advisor_followup_email(user) -> bool:
    # Only send if advisor_ready was sent but follow-up hasn't been sent yet
    if not _already_sent(user, EmailLog.ADVISOR_READY):
        return False
    if _already_sent(user, EmailLog.ADVISOR_FOLLOWUP):
        return False

    subject = "Still thinking about your next step?"
    body = f"""Hi {user.first_name or 'there'},

You may be ready to explore your options.

Speak to a mortgage advisor: {settings.FRONTEND_URL}/dashboard

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.ADVISOR_FOLLOWUP, subject, body)


# ------------------------------------------------------------------
# 11. 30-day re-engagement  (Trigger: user_inactive_30_days)
# ------------------------------------------------------------------

def send_reengagement_email(user) -> bool:
    if _already_sent(user, EmailLog.REMINDER_30, within_days=30):
        return False

    subject = "Are you still planning to buy a home?"
    body = f"""Hi {user.first_name or 'there'},

Your situation may have changed.

Check your readiness now: {settings.FRONTEND_URL}/dashboard/assessment

— Team Rendi

This is an estimate for information only. Not financial advice."""

    return _send(user, EmailLog.REMINDER_30, subject, body)
