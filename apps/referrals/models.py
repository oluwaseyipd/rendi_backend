import secrets
from django.conf import settings
from django.db import models


def generate_referral_code():
    """Generates a short, URL-safe unique referral code."""
    return secrets.token_urlsafe(8)  # e.g. "aB3xZ9kQ"


class Referral(models.Model):
    """
    One record per user — their referral identity.
    Tracks how many people they invited and how many signed up.
    """

    # The user who owns this referral code
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral",
    )

    # Unique shareable code — embedded in the registration URL
    code = models.CharField(
        max_length=20,
        unique=True,
        default=generate_referral_code,
    )

    # Running totals — updated on each event
    invite_count    = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Referral"
        verbose_name_plural = "Referrals"

    def __str__(self):
        return (
            f"{self.user.email} — code: {self.code} "
            f"({self.invite_count} invites, {self.conversion_count} conversions)"
        )

    @property
    def referral_url(self) -> str:
        """Full registration URL with this code pre-attached."""
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url}/auth/register?ref={self.code}"

    @property
    def conversion_rate(self) -> float:
        """Percentage of invites that converted to sign-ups."""
        if self.invite_count == 0:
            return 0.0
        return round((self.conversion_count / self.invite_count) * 100, 1)


class ReferralConversion(models.Model):
    """
    Records each individual conversion — one row per referred sign-up.
    Linked to both the referrer and the new user who signed up.
    """

    referral = models.ForeignKey(
        Referral,
        on_delete=models.CASCADE,
        related_name="conversions",
    )

    # The user who signed up via this referral code
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referred_by",
        null=True,
        blank=True,
    )

    converted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Referral conversion"
        verbose_name_plural = "Referral conversions"
        ordering = ["-converted_at"]

    def __str__(self):
        referred = self.referred_user.email if self.referred_user else "unknown"
        return f"{self.referral.user.email} → {referred}"