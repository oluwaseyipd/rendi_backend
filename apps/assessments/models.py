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
    score = models.PositiveSmallIntegerField()   # 0–100
    status = models.CharField(max_length=50)     # "Early stages" | "Getting closer" | "Nearly ready"
    time_estimate = models.CharField(max_length=100)

    # --- Deposit helpers ---
    deposit_needed = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_gap = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_months = models.PositiveSmallIntegerField()

    # --- Component breakdown (stored as JSON for flexibility) ---
    breakdown = models.JSONField(default=dict)

    # --- Action plan ---
    action_plan = models.JSONField(default=list)

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Assessment"
        verbose_name_plural = "Assessments"

    def __str__(self):
        return f"{self.user.email} — {self.status} ({self.score}/100) @ {self.created_at:%Y-%m-%d %H:%M}"
