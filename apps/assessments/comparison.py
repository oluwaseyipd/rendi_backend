"""
apps/assessments/comparison.py
--------------------------------
"How you compare" feature — pure calculation engine.

Spec reference: Rendi 'How you compare' Feature CTO implementation guide

All calculations are read-only aggregate queries.
No data is written here.
"""

from dataclasses import dataclass
from typing import Optional
from django.conf import settings
from django.db.models import Avg, Count


# ------------------------------------------------------------------
# Income band definitions
# ------------------------------------------------------------------

INCOME_BANDS = [
    (0,      20_000,  "Under £20k"),
    (20_000, 30_000,  "£20k–£30k"),
    (30_000, 40_000,  "£30k–£40k"),
    (40_000, 50_000,  "£40k–£50k"),
    (50_000, 70_000,  "£50k–£70k"),
    (70_000, 999_999, "£70k+"),
]


def get_income_band(annual_income: float) -> tuple[float, float, str]:
    """Returns (min, max, label) for the user's income band."""
    for band_min, band_max, label in INCOME_BANDS:
        if band_min <= annual_income < band_max:
            return band_min, band_max, label
    return INCOME_BANDS[-1]


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------

@dataclass
class ComparisonResult:
    # Whether there is enough data to show comparison
    has_data: bool

    # If has_data is False, show this fallback message instead
    fallback_message: str

    # Main percentile statement
    headline: str           # "You are ahead of 62% of users"
    headline_pct: int       # 62

    # Supporting lines
    subtitle: str           # "Most users in your income range are 2-3 years away"
    savings_line: str       # "People earning similar to you have saved £8,000 on average"
    deposit_gap_line: str   # "Your deposit gap is smaller than the average user in your group"

    # Segment context
    segment_label: str      # "users earning £40k–£50k"
    total_users: int        # how many total scored users

    # Share text for referral flow
    share_text: str


# ------------------------------------------------------------------
# Main comparison function
# ------------------------------------------------------------------

def calculate_comparison(user_assessment) -> ComparisonResult:
    """
    Calculates comparison data for a given assessment.

    Returns ComparisonResult with has_data=False and a fallback message
    if the minimum data thresholds aren't met.
    """
    from apps.assessments.models import Assessment

    min_total   = getattr(settings, "COMPARISON_MIN_TOTAL_USERS", 100)
    min_segment = getattr(settings, "COMPARISON_MIN_SEGMENT_USERS", 30)

    user_score  = user_assessment.score
    user_income = float(user_assessment.annual_income)
    user_gap    = float(user_assessment.deposit_gap)
    user_months = user_assessment.estimated_months

    # ── Total scored users ────────────────────────────────────────
    all_assessments = Assessment.objects.all()
    total_count = all_assessments.count()

    if total_count < min_total:
        return ComparisonResult(
            has_data=False,
            fallback_message=(
                "We'll show comparison insights once more users in your group "
                "complete their assessment."
            ),
            headline="", headline_pct=0,
            subtitle="", savings_line="", deposit_gap_line="",
            segment_label="", total_users=total_count,
            share_text="",
        )

    # ── Score percentile (overall) ────────────────────────────────
    # Count users who scored strictly below the current user
    users_below = all_assessments.filter(score__lt=user_score).count()
    percentile  = round((users_below / total_count) * 100)

    # Friendly percentile copy per spec
    if percentile >= 60:
        headline = f"You are ahead of {percentile}% of users."
    elif percentile >= 40:
        headline = f"You are progressing well and are ahead of {percentile}% of users."
    else:
        headline = "You are in the early stages — many users start here."

    # ── Income-band segment ───────────────────────────────────────
    band_min, band_max, band_label = get_income_band(user_income)

    segment_qs = all_assessments.filter(
        annual_income__gte=band_min,
        annual_income__lt=band_max,
    )
    segment_count = segment_qs.count()

    if segment_count < min_segment:
        # Not enough segment data — use softer stage-based comparison
        stage_qs    = all_assessments.filter(status=user_assessment.status)
        stage_count = stage_qs.count()

        subtitle      = f"Most users in your stage are working toward the same goal."
        savings_line  = ""
        deposit_line  = ""
        segment_label = f"users at the {user_assessment.status} stage"

    else:
        # ── Segment averages ──────────────────────────────────────
        agg = segment_qs.aggregate(
            avg_savings=Avg("savings"),
            avg_months=Avg("estimated_months"),
            avg_gap=Avg("deposit_gap"),
        )

        avg_savings = agg["avg_savings"] or 0
        avg_months  = agg["avg_months"]  or 0
        avg_gap     = agg["avg_gap"]     or 0

        # ── Timeline line ─────────────────────────────────────────
        if avg_months <= 6:
            timeline_str = "under 6 months"
        elif avg_months <= 12:
            timeline_str = "6–12 months"
        elif avg_months <= 18:
            timeline_str = "12–18 months"
        elif avg_months <= 36:
            timeline_str = "1–3 years"
        else:
            timeline_str = "3+ years"

        subtitle = (
            f"Most users in your income range are {timeline_str} away from buying."
        )

        # ── Savings line ──────────────────────────────────────────
        avg_savings_fmt = f"£{int(avg_savings):,}"
        savings_line = (
            f"People earning similar to you have saved {avg_savings_fmt} on average."
        )

        # ── Deposit gap comparison ────────────────────────────────
        if user_gap < avg_gap:
            deposit_line = "Your deposit gap is smaller than the average user in your group."
        elif user_gap > avg_gap:
            deposit_line = "Your deposit gap is larger than the average user in your group."
        else:
            deposit_line = "Your deposit gap is about average for users in your group."

        deposit_gap_line = deposit_line
        segment_label    = f"users earning {band_label}"

    # ── Share text ────────────────────────────────────────────────
    share_text = (
        f"I just checked how close I am to buying a home on Rendi. "
        f"I am ahead of {percentile}% of users. "
        f"Want to see where you stand?"
    )

    return ComparisonResult(
        has_data=True,
        fallback_message="",
        headline=headline,
        headline_pct=percentile,
        subtitle=subtitle,
        savings_line=savings_line if segment_count >= min_segment else "",
        deposit_gap_line=deposit_gap_line if segment_count >= min_segment else "",
        segment_label=segment_label,
        total_users=total_count,
        share_text=share_text,
    )
