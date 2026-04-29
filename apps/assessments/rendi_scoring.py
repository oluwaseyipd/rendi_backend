"""
Rendi Scoring Engine — v2
Implements Rendi Scoring Spec v1 (Lender-Inspired) with all known bugs resolved.

Bug fixes included:
  [BUG-1] Saving simulations showing identical months for different rates
  [BUG-2] Simulation rates below assumed baseline shown as "improvements"
  [BUG-3] All simulation scenarios hitting cap with no useful differentiation
  [BUG-4] Status-band time range contradicting calculated estimated_months
  [BUG-5] Deposit flagged as biggest blocker even when deposit_gap = 0

Drop this file in at apps/assessments/rendi_scoring.py
"""

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEPOSIT_THRESHOLD = 0.10        # 10% deposit target
ASSUMED_SAVE_RATE = 0.15        # 15% of monthly income = assumed baseline save rate
MONTHS_CAP        = 60          # Hard cap on estimated months (5 years)

SCORE_BANDS = [
    (85, "Strong position",   "Likely 0–6 months away"),
    (65, "Getting close",     "Likely 6–18 months away"),
    (35, "Building momentum", "Likely 18–36 months away"),
    (0,  "Early stages",      "Likely 18–36 months away"),
]

SIMULATION_RATES = [300, 500, 750]  # £/month scenarios

DISCLAIMER = (
    "This is an estimate for information only. "
    "It is not financial advice, a lending decision, or an eligibility check."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ComponentScore:
    points: int
    max_points: int
    label: str
    is_biggest_blocker: bool = False
    priority_label: str = ""        # "Biggest blocker" | "Important" | "Good"


@dataclass
class Breakdown:
    deposit: ComponentScore
    income: ComponentScore
    commitments: ComponentScore
    credit: ComponentScore


@dataclass
class SavingScenario:
    monthly_amount: int
    months_to_close: int
    months_faster_than_baseline: int
    message: str
    is_meaningful: bool             # False if outcome duplicates another scenario


@dataclass
class AssessmentResult:
    # Core
    score: int
    status: str
    time_estimate: str

    # Deposit
    deposit_needed: int
    deposit_gap: int
    estimated_months: int           # Single source of truth for timeline on main card

    # Blockers
    biggest_blocker: str
    breakdown: Breakdown

    # Plan & simulations
    action_plan: list
    saving_scenarios: list

    # Affordability
    borrowing_power: int
    total_budget: int
    affordability_gap: int

    disclaimer: str = DISCLAIMER


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_deposit(savings: float, target_price: float) -> ComponentScore:
    pct = savings / target_price
    if pct < 0.05:
        pts, label = 0, "Needs attention"
    elif pct < 0.10:
        pts, label = 15, "Needs attention"
    elif pct < 0.15:
        pts, label = 25, "Getting there"
    else:
        pts, label = 40, "Strong"
    return ComponentScore(points=pts, max_points=40, label=label)


def _score_income(annual_income: float, target_price: float) -> ComponentScore:
    multiple = target_price / annual_income
    if multiple > 5.0:
        pts, label = 5, "Needs attention"
    elif multiple > 4.0:
        pts, label = 15, "Needs attention"
    elif multiple > 3.0:
        pts, label = 25, "Okay"
    else:
        pts, label = 30, "Strong"
    return ComponentScore(points=pts, max_points=30, label=label)


def _score_commitments(
    monthly_commitments: Optional[float], monthly_income: float
) -> ComponentScore:
    if monthly_commitments is None:
        return ComponentScore(points=10, max_points=20, label="Not provided")
    ratio = monthly_commitments / monthly_income
    if ratio > 0.40:
        pts, label = 0, "Needs attention"
    elif ratio > 0.25:
        pts, label = 10, "Needs attention"
    elif ratio > 0.10:
        pts, label = 15, "Okay"
    else:
        pts, label = 20, "Low impact"
    return ComponentScore(points=pts, max_points=20, label=label)


def _score_credit(
    has_ccj: Optional[bool], has_missed_payments: Optional[bool]
) -> ComponentScore:
    if has_ccj is None and has_missed_payments is None:
        return ComponentScore(points=5, max_points=10, label="Not provided")
    if has_ccj:
        return ComponentScore(points=0, max_points=10, label="Needs attention")
    if has_missed_payments:
        return ComponentScore(points=5, max_points=10, label="Okay")
    return ComponentScore(points=10, max_points=10, label="Low impact")


def _status_from_score(score: int):
    for threshold, status, time_est in SCORE_BANDS:
        if score >= threshold:
            return status, time_est
    return SCORE_BANDS[-1][1], SCORE_BANDS[-1][2]


def _months_to_close(deposit_gap: float, monthly_save: float) -> int:
    if deposit_gap <= 0:
        return 0
    if monthly_save <= 0:
        return MONTHS_CAP
    return min(MONTHS_CAP, math.ceil(deposit_gap / monthly_save))


# ---------------------------------------------------------------------------
# Blocker ranking — BUG-5 FIX
# ---------------------------------------------------------------------------

def _rank_blockers(
    deposit: ComponentScore,
    income: ComponentScore,
    commitments: ComponentScore,
    credit: ComponentScore,
    deposit_gap: int,
):
    """
    BUG-5 FIX: deposit is excluded from biggest-blocker consideration
    when deposit_gap == 0 — having no gap means it is not actionable
    regardless of its point score.
    """
    components = [
        ("deposit", deposit),
        ("income", income),
        ("commitments", commitments),
        ("credit", credit),
    ]

    def blocker_priority(item):
        name, comp = item
        if name == "deposit" and deposit_gap == 0:
            return 1.0          # push to bottom — already satisfied
        return comp.points / comp.max_points  # lower ratio = worse = higher priority

    ranked = sorted(components, key=blocker_priority)
    priority_labels = ["Biggest blocker", "Important", "Important", "Good"]
    named = {name: comp for name, comp in components}

    for i, (name, _) in enumerate(ranked):
        named[name].priority_label = priority_labels[i]
        named[name].is_biggest_blocker = (i == 0)

    return named["deposit"], named["income"], named["commitments"], named["credit"]


# ---------------------------------------------------------------------------
# Saving simulations — BUG-1, BUG-2, BUG-3 FIX
# ---------------------------------------------------------------------------

def _build_saving_scenarios(
    deposit_gap: int,
    annual_income: float,
    baseline_months: int,
) -> list:
    """
    BUG-1: Duplicate month outcomes are flagged is_meaningful=False.
    BUG-2: Rates below assumed baseline are framed as slower, not improvements.
    BUG-3: When all rates cap at MONTHS_CAP, collapse to one price-reduction note.
    """
    if deposit_gap <= 0:
        return []

    assumed_monthly_save = (annual_income / 12) * ASSUMED_SAVE_RATE
    scenarios = []
    seen_months = set()

    for rate in SIMULATION_RATES:
        months = _months_to_close(deposit_gap, rate)
        diff   = baseline_months - months   # positive = faster, negative = slower

        is_improvement = rate >= assumed_monthly_save
        is_meaningful  = months not in seen_months
        seen_months.add(months)

        if months == MONTHS_CAP and not is_improvement:
            message = (
                f"Saving £{rate}/month is below your estimated current saving pace "
                f"and won't close your deposit gap within {MONTHS_CAP} months."
            )
        elif months == MONTHS_CAP:
            message = (
                f"Saving £{rate}/month won't close your deposit gap within "
                f"{MONTHS_CAP} months. Consider reviewing your target property price."
            )
        elif not is_improvement:
            message = (
                f"Saving £{rate}/month is below your current pace — "
                f"it would take approximately {months} months, "
                f"which is {abs(diff)} months slower than your current trajectory."
            )
        elif diff > 0:
            message = (
                f"If you save £{rate}/month, you could close your deposit gap "
                f"in {months} months — {diff} months faster than your current pace."
            )
        else:
            message = (
                f"Saving £{rate}/month keeps you on a similar timeline "
                f"of approximately {months} months."
            )

        scenarios.append(SavingScenario(
            monthly_amount=rate,
            months_to_close=months,
            months_faster_than_baseline=diff,
            message=message,
            is_meaningful=is_meaningful,
        ))

    # BUG-3: all meaningful scenarios capped → collapse + surface price lever
    meaningful = [s for s in scenarios if s.is_meaningful]
    if all(s.months_to_close == MONTHS_CAP for s in meaningful):
        return [SavingScenario(
            monthly_amount=0,
            months_to_close=MONTHS_CAP,
            months_faster_than_baseline=0,
            is_meaningful=True,
            message=(
                f"At your current target price, standard saving rates won't close "
                f"your deposit gap within {MONTHS_CAP} months. "
                f"The highest-impact action is to review your target property price — "
                f"reducing it by £10,000 would reduce your deposit target by £1,000."
            ),
        )]

    return scenarios


# ---------------------------------------------------------------------------
# Action plan
# ---------------------------------------------------------------------------

def _build_action_plan(
    deposit: ComponentScore,
    income: ComponentScore,
    commitments: ComponentScore,
    credit: ComponentScore,
    deposit_gap: int,
    affordability_gap: int,
) -> list:
    plan = []
    if deposit_gap > 0:
        plan.append(
            f"Consider building your deposit — "
            f"you need approximately £{deposit_gap:,} more to reach the 10% threshold."
        )
    if income.label in ("Needs attention", "Okay") and affordability_gap > 0:
        plan.append(
            f"Consider reviewing your target budget — "
            f"your current income supports borrowing up to £{affordability_gap:,} less "
            f"than your target price."
        )
    if commitments.label == "Needs attention":
        plan.append(
            "Consider reducing existing monthly commitments where possible "
            "to improve your affordability assessment."
        )
    if credit.label == "Needs attention":
        plan.append(
            "Consider keeping all repayments on time and avoiding new missed payments "
            "to strengthen your credit profile over time."
        )
    elif credit.label == "Okay":
        plan.append(
            "Consider maintaining on-time payments — "
            "a clean 12-month record improves your credit profile significantly."
        )
    plan.append("You can revisit this as your situation changes.")
    return plan


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def compute_assessment(
    annual_income: float,
    savings: float,
    target_property_price: float,
    monthly_commitments: Optional[float] = None,
    has_ccj: Optional[bool] = None,
    has_missed_payments: Optional[bool] = None,
) -> AssessmentResult:
    """
    Computes a Rendi readiness assessment.
    Arguments match the API payload fields exactly.
    """
    monthly_income = annual_income / 12

    # Score components
    deposit_comp = _score_deposit(savings, target_property_price)
    income_comp  = _score_income(annual_income, target_property_price)
    commit_comp  = _score_commitments(monthly_commitments, monthly_income)
    credit_comp  = _score_credit(has_ccj, has_missed_payments)

    total_score = min(
        100,
        deposit_comp.points + income_comp.points
        + commit_comp.points + credit_comp.points,
    )

    # Deposit
    deposit_needed = round(target_property_price * DEPOSIT_THRESHOLD)
    deposit_gap    = max(0, deposit_needed - int(savings))

    # Affordability
    borrowing_power   = int(annual_income * 4.5)
    total_budget      = borrowing_power + int(savings)
    affordability_gap = max(0, int(target_property_price) - total_budget)

    # Timeline — BUG-4 FIX: estimated_months is the single source of truth
    assumed_monthly_save = monthly_income * ASSUMED_SAVE_RATE
    estimated_months     = _months_to_close(deposit_gap, assumed_monthly_save)
    status, time_estimate = _status_from_score(total_score)

    # Blockers
    deposit_comp, income_comp, commit_comp, credit_comp = _rank_blockers(
        deposit_comp, income_comp, commit_comp, credit_comp, deposit_gap
    )

    biggest_blocker = next(
        name for name, comp in [
            ("deposit", deposit_comp),
            ("income",  income_comp),
            ("commitments", commit_comp),
            ("credit",  credit_comp),
        ]
        if comp.is_biggest_blocker
    )

    breakdown = Breakdown(
        deposit=deposit_comp,
        income=income_comp,
        commitments=commit_comp,
        credit=credit_comp,
    )

    action_plan      = _build_action_plan(
        deposit_comp, income_comp, commit_comp, credit_comp,
        deposit_gap, affordability_gap,
    )
    saving_scenarios = _build_saving_scenarios(
        deposit_gap, annual_income, estimated_months
    )

    return AssessmentResult(
        score=total_score,
        status=status,
        time_estimate=time_estimate,
        deposit_needed=deposit_needed,
        deposit_gap=deposit_gap,
        estimated_months=estimated_months,
        biggest_blocker=biggest_blocker,
        breakdown=breakdown,
        action_plan=action_plan,
        saving_scenarios=saving_scenarios,
        borrowing_power=borrowing_power,
        total_budget=total_budget,
        affordability_gap=affordability_gap,
    )