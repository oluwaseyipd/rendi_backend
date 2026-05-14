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

    # --- Inputs ---
    annual_income         = models.DecimalField(max_digits=12, decimal_places=2)
    savings               = models.DecimalField(max_digits=12, decimal_places=2)
    target_property_price = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_commitments   = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    has_ccj             = models.BooleanField(null=True, blank=True)
    has_missed_payments = models.BooleanField(null=True, blank=True)

    # --- Core outputs ---
    score         = models.PositiveSmallIntegerField()
    status        = models.CharField(max_length=50)
    time_estimate = models.CharField(max_length=100)

    # --- Deposit helpers ---
    deposit_needed   = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_gap      = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_months = models.PositiveSmallIntegerField()

    # --- Component breakdown ---
    # Shape: {deposit, income, commitments, credit} each with:
    #   points, max_points, label, priority_label, is_biggest_blocker
    breakdown = models.JSONField(default=dict)

    # --- Blocker fields ---
    # biggest_blocker: key of the highest-deficit component
    #   values: "deposit" | "income" | "commitments" | "credit"
    biggest_blocker = models.CharField(max_length=20, default="deposit")

    # blocker_priority: all 4 components ranked worst → best
    #   e.g. [{"component": "deposit", "priority_label": "Biggest blocker"}, ...]
    blocker_priority = models.JSONField(default=list)

    # --- Plan & simulations ---
    # action_plan: list of plain-English guidance strings
    action_plan = models.JSONField(default=list)

    # recommendations: kept in sync with action_plan for backwards compatibility
    recommendations = models.JSONField(default=list)

    # simulations: saving scenarios from the fastest-improvement engine
    # Shape per item: {monthly_amount, months_to_close,
    #                  months_faster_than_baseline, message, is_meaningful}
    simulations = models.JSONField(default=list)

    # --- Affordability (new in v2) ---
    # borrowing_power  = annual_income × 4.5
    # total_budget     = borrowing_power + savings
    # affordability_gap = max(0, target_price - total_budget)
    borrowing_power   = models.PositiveIntegerField(default=0)
    total_budget      = models.PositiveIntegerField(default=0)
    affordability_gap = models.PositiveIntegerField(default=0)

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