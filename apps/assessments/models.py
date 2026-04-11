from django.conf import settings
from django.db import models


class Assessment(models.Model):
    """
    Stores every readiness assessment submission.
    Each submit creates a new record — history is preserved, nothing overwritten.
    """

    # --- Ownership ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessments",
    )

    # --- Inputs (what the user entered) ---
    annual_income = models.DecimalField(max_digits=12, decimal_places=2)
    savings = models.DecimalField(max_digits=12, decimal_places=2)
    target_property_price = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_commitments = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    has_ccj = models.BooleanField(null=True, blank=True)
    has_missed_payments = models.BooleanField(null=True, blank=True)

    # --- Core outputs ---
    score = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=50)
    time_estimate = models.CharField(max_length=100)

    # --- Deposit helpers ---
    deposit_needed = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_gap = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_months = models.PositiveSmallIntegerField()

    # --- Component breakdown ---
    breakdown = models.JSONField(default=dict)

    # --- Phase 1: Biggest blocker ---
    # Stores the key of the component with the highest deficit
    # e.g. "deposit" | "income" | "commitments" | "credit"
    biggest_blocker = models.CharField(max_length=20, default="deposit")

    # All 4 components ranked worst to best
    blocker_priority = models.JSONField(default=list)

    # --- Phase 1: Quantified personalised recommendations ---
    # Replaces generic action_plan strings with calculated ones
    recommendations = models.JSONField(default=list)

    # --- Phase 1: Fastest-improvement simulations ---
    # List of saving scenarios with revised timelines
    simulations = models.JSONField(default=list)

    # --- Legacy action plan (kept for backwards compatibility) ---
    action_plan = models.JSONField(default=list)

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Assessment"
        verbose_name_plural = "Assessments"

    def __str__(self):
        return (
            f"{self.user.email} — {self.status} ({self.score}/100) "
            f"| Blocker: {self.biggest_blocker} "
            f"@ {self.created_at:%Y-%m-%d %H:%M}"
        )