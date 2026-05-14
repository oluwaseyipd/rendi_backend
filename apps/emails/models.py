from django.conf import settings
from django.db import models


class EmailLog(models.Model):
    """
    Records every email sent to a user.
    Used to:
      - Prevent duplicate sends (idempotency check before every send)
      - Track open/click rates when webhooks are added later
      - Audit trail for debugging
    """

    # ── Email type keys — match trigger names from the spec ──────
    WELCOME              = "welcome"
    RESULTS              = "results"
    REMINDER_7           = "reminder_7"
    REMINDER_14          = "reminder_14"
    REMINDER_30          = "reminder_30"
    PROGRESS             = "progress"
    DEPOSIT_BLOCKER      = "deposit_blocker"
    FASTEST_IMPROVEMENT  = "fastest_improvement"
    NEAR_READY           = "near_ready"
    ADVISOR_READY        = "advisor_ready"
    ADVISOR_FOLLOWUP     = "advisor_followup"

    EMAIL_TYPE_CHOICES = [
        (WELCOME,             "Welcome"),
        (RESULTS,             "Results"),
        (REMINDER_7,          "7-day reminder"),
        (REMINDER_14,         "14-day reminder"),
        (REMINDER_30,         "30-day re-engagement"),
        (PROGRESS,            "Progress update"),
        (DEPOSIT_BLOCKER,     "Deposit blocker"),
        (FASTEST_IMPROVEMENT, "Fastest improvement"),
        (NEAR_READY,          "Near ready"),
        (ADVISOR_READY,       "Advisor ready"),
        (ADVISOR_FOLLOWUP,    "Advisor follow-up"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_logs",
    )
    email_type  = models.CharField(max_length=30, choices=EMAIL_TYPE_CHOICES)
    subject     = models.CharField(max_length=255)
    sent_at     = models.DateTimeField(auto_now_add=True)
    success     = models.BooleanField(default=True)
    error       = models.TextField(blank=True, default="")

    # Optional: link to the assessment that triggered this email
    assessment  = models.ForeignKey(
        "assessments.Assessment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Email log"
        verbose_name_plural = "Email logs"
        # Composite index for fast duplicate checks
        indexes = [
            models.Index(fields=["user", "email_type", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} | {self.email_type} | {self.sent_at:%Y-%m-%d %H:%M}"
