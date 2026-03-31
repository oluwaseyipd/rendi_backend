"""
rendi_scoring.py
----------------
Deterministic readiness scoring engine for Rendi MVP.

Based on: Rendi Scoring Spec v1 (Lender-Inspired, Logic-Only)

All outputs are INFORMATIONAL ESTIMATES ONLY.
This is not financial advice, a lending decision, or an eligibility check.
"""

from dataclasses import dataclass
from typing import Optional


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class ScoringInputs:
    annual_income: float            # required
    savings: float                  # required (deposit pot)
    target_property_price: float    # required
    monthly_commitments: Optional[float] = None   # optional (debts/outgoings)
    has_ccj: Optional[bool] = None                # optional — CCJ in last 6 years?
    has_missed_payments: Optional[bool] = None    # optional — missed payments in last 12 months?


@dataclass
class ComponentBreakdown:
    points: int
    max_points: int
    label: str        # "Needs attention" | "Okay" | "Strong"
    value: float      # the raw ratio/percentage used


@dataclass
class ScoringResult:
    # Core
    score: int                       # 0–100
    status: str                      # "Early stages" | "Getting closer" | "Nearly ready"
    time_estimate: str               # human-readable time estimate

    # Component breakdown
    deposit_breakdown: ComponentBreakdown
    income_breakdown: ComponentBreakdown
    commitments_breakdown: ComponentBreakdown
    credit_breakdown: ComponentBreakdown

    # Deposit helpers
    deposit_needed: float            # 10% benchmark (educational)
    deposit_gap: float               # how much more needed
    estimated_months: int            # months to close gap (capped at 60)

    # Action plan
    action_plan: list[str]

    # Regulatory disclaimer
    disclaimer: str


# ------------------------------------------------------------------
# Constants / thresholds (easy to reconfigure)
# ------------------------------------------------------------------

DEPOSIT_BENCHMARK_PERCENT = 0.10     # 10% educational benchmark
ASSUMED_SAVINGS_RATE = 0.15          # assume user saves 15% of monthly income
MAX_ESTIMATED_MONTHS = 60

STATUS_THRESHOLDS = {
    "nearly_ready": 70,
    "getting_closer": 40,
}

TIME_ESTIMATES = {
    "Nearly ready": "Likely 0–6 months away",
    "Getting closer": "Likely 6–18 months away",
    "Early stages": "Likely 18–36 months away",
}

DISCLAIMER = "This is an estimate for information only. It is not financial advice, a mortgage offer, or an eligibility decision."


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


# ------------------------------------------------------------------
# Component scorers
# ------------------------------------------------------------------

def _score_deposit(savings: float, price: float) -> ComponentBreakdown:
    """
    deposit_percent = savings / target_price
    < 5%      → 0 pts   → Needs attention
    5–9%      → 15 pts  → Needs attention
    10–14%    → 25 pts  → Getting there
    ≥ 15%     → 40 pts  → Strong
    """
    deposit_percent = savings / price if price > 0 else 0

    if deposit_percent >= 0.15:
        points, label = 40, "Strong"
    elif deposit_percent >= 0.10:
        points, label = 25, "Getting there"
    elif deposit_percent >= 0.05:
        points, label = 15, "Needs attention"
    else:
        points, label = 0, "Needs attention"

    return ComponentBreakdown(
        points=points,
        max_points=40,
        label=label,
        value=round(deposit_percent * 100, 2),   # store as percentage
    )


def _score_income(income: float, price: float) -> ComponentBreakdown:
    """
    income_multiple = target_price / annual_income
    > 5.0x      → 5 pts  → Needs attention
    4.1–5.0x    → 15 pts → Needs attention
    3.1–4.0x    → 25 pts → Okay
    ≤ 3.0x      → 30 pts → Strong
    """
    income_multiple = price / income if income > 0 else 9999

    if income_multiple <= 3.0:
        points, label = 30, "Strong"
    elif income_multiple <= 4.0:
        points, label = 25, "Okay"
    elif income_multiple <= 5.0:
        points, label = 15, "Needs attention"
    else:
        points, label = 5, "Needs attention"

    return ComponentBreakdown(
        points=points,
        max_points=30,
        label=label,
        value=round(income_multiple, 2),
    )


def _score_commitments(
    monthly_commitments: Optional[float], monthly_income: float
) -> ComponentBreakdown:
    """
    commitment_ratio = monthly_commitments / monthly_income
    If skipped → 10 pts (neutral)
    > 40%       → 0 pts  → Needs attention
    26–40%      → 10 pts → Needs attention
    11–25%      → 15 pts → Okay
    ≤ 10%       → 20 pts → Low impact
    """
    if monthly_commitments is None:
        return ComponentBreakdown(
            points=10, max_points=20, label="Not provided", value=-1
        )

    commitment_ratio = (
        monthly_commitments / monthly_income if monthly_income > 0 else 9999
    )

    if commitment_ratio <= 0.10:
        points, label = 20, "Low impact"
    elif commitment_ratio <= 0.25:
        points, label = 15, "Okay"
    elif commitment_ratio <= 0.40:
        points, label = 10, "Needs attention"
    else:
        points, label = 0, "Needs attention"

    return ComponentBreakdown(
        points=points,
        max_points=20,
        label=label,
        value=round(commitment_ratio * 100, 2),
    )


def _score_credit(
    has_ccj: Optional[bool], has_missed_payments: Optional[bool]
) -> ComponentBreakdown:
    """
    CCJ = Yes              → 0 pts  → Needs attention
    Missed payments only   → 5 pts  → Okay
    Neither                → 10 pts → Low impact
    Skipped                → 5 pts  (neutral)
    """
    if has_ccj is None and has_missed_payments is None:
        # Both skipped
        return ComponentBreakdown(
            points=5, max_points=10, label="Not provided", value=-1
        )

    if has_ccj:
        points, label = 0, "Needs attention"
    elif has_missed_payments:
        points, label = 5, "Okay"
    else:
        points, label = 10, "Low impact"

    return ComponentBreakdown(
        points=points,
        max_points=10,
        label=label,
        value=-1,   # boolean input; no numeric ratio
    )


# ------------------------------------------------------------------
# Action plan generator
# ------------------------------------------------------------------

def _build_action_plan(
    deposit_bd: ComponentBreakdown,
    income_bd: ComponentBreakdown,
    commitments_bd: ComponentBreakdown,
    credit_bd: ComponentBreakdown,
) -> list[str]:
    plan = []

    if deposit_bd.label in ("Needs attention",):
        plan.append("Consider building your deposit over time to strengthen your position.")

    if income_bd.label == "Needs attention":
        plan.append(
            "Consider reviewing your target budget or extending your timeframe "
            "based on what you entered."
        )

    if commitments_bd.label == "Needs attention":
        plan.append(
            "Consider reducing existing balances or outgoings where possible "
            "to improve your affordability picture."
        )

    if credit_bd.label == "Needs attention":
        plan.append(
            "Consider keeping repayments on time and avoiding missed payments "
            "going forward."
        )
    elif credit_bd.label == "Okay" and credit_bd.points == 5:
        plan.append(
            "Consider keeping repayments up to date — a consistent payment "
            "history can help over time."
        )

    plan.append("You can revisit this estimate as your situation changes.")
    return plan


# ------------------------------------------------------------------
# Main scoring function
# ------------------------------------------------------------------

def calculate_readiness(inputs: ScoringInputs) -> ScoringResult:
    """
    Entry point. Accepts a ScoringInputs instance and returns a ScoringResult.
    All computations are deterministic and rule-based — no external APIs.
    """
    # Sanitise inputs
    income = max(0.0, inputs.annual_income)
    savings = max(0.0, inputs.savings)
    price = max(1.0, inputs.target_property_price)
    monthly_income = income / 12

    # --- Component scores ---
    deposit_bd = _score_deposit(savings, price)
    income_bd = _score_income(income, price)
    commitments_bd = _score_commitments(inputs.monthly_commitments, monthly_income)
    credit_bd = _score_credit(inputs.has_ccj, inputs.has_missed_payments)

    # --- Total score ---
    raw_score = (
        deposit_bd.points
        + income_bd.points
        + commitments_bd.points
        + credit_bd.points
    )
    score = int(_clamp(raw_score, 0, 100))

    # --- Status & time estimate ---
    if score >= STATUS_THRESHOLDS["nearly_ready"]:
        status = "Nearly ready"
    elif score >= STATUS_THRESHOLDS["getting_closer"]:
        status = "Getting closer"
    else:
        status = "Early stages"

    time_estimate = TIME_ESTIMATES[status]

    # --- Deposit helpers ---
    deposit_needed = round(price * DEPOSIT_BENCHMARK_PERCENT)
    deposit_gap = round(max(0.0, deposit_needed - savings))

    assumed_monthly_save = max(0.0, monthly_income * ASSUMED_SAVINGS_RATE)
    if deposit_gap > 0:
        estimated_months = (
            int(_clamp(
                -(-deposit_gap // assumed_monthly_save),   # ceiling division
                0, MAX_ESTIMATED_MONTHS
            ))
            if assumed_monthly_save > 0
            else MAX_ESTIMATED_MONTHS
        )
    else:
        estimated_months = 0

    # --- Action plan ---
    action_plan = _build_action_plan(
        deposit_bd, income_bd, commitments_bd, credit_bd
    )

    return ScoringResult(
        score=score,
        status=status,
        time_estimate=time_estimate,
        deposit_breakdown=deposit_bd,
        income_breakdown=income_bd,
        commitments_breakdown=commitments_bd,
        credit_breakdown=credit_bd,
        deposit_needed=deposit_needed,
        deposit_gap=deposit_gap,
        estimated_months=estimated_months,
        action_plan=action_plan,
        disclaimer=DISCLAIMER,
    )
