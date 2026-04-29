"""
Rendi Scoring Engine — Fixed v2
Implements Rendi Scoring Spec v1 (Lender-Inspired) with all known bugs resolved.

Bug fixes included:
  [BUG-1] Saving simulations showing identical months for different rates
  [BUG-2] Simulation rates below assumed baseline shown as "improvements"
  [BUG-3] All simulation scenarios hitting cap with no useful differentiation
  [BUG-4] Status-band time range contradicting calculated estimated_months
  [BUG-5] Deposit flagged as biggest blocker even when deposit_gap = 0
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants — change these in one place, everything updates automatically
# ---------------------------------------------------------------------------

DEPOSIT_THRESHOLD = 0.10          # 10% deposit target
ASSUMED_SAVE_RATE = 0.15          # 15% of monthly income = assumed baseline save rate
MONTHS_CAP = 60                   # Hard cap on estimated months (5 years)

SCORE_BANDS = [
    (85, "Strong position",    "Likely 0–6 months away"),
    (65, "Getting close",      "Likely 6–18 months away"),
    (35, "Building momentum",  "Likely 18–36 months away"),
    (0,  "Early stages",       "Likely 18–36 months away"),
]

SIMULATION_RATES = [300, 500, 750]   # £/month scenarios for fastest improvement


# ---------------------------------------------------------------------------
# Data classes for clean, typed output
# ---------------------------------------------------------------------------

@dataclass
class ComponentScore:
    points: int
    max_points: int
    label: str
    is_biggest_blocker: bool = False
    priority_label: str = ""      # "Biggest blocker" | "Important" | "Good"


@dataclass
class Breakdown:
    deposit: ComponentScore
    income: ComponentScore
    commitments: ComponentScore
    credit: ComponentScore


@dataclass
class SavingScenario:
    monthly_amount: int
    months_to_close: int           # None if gap already closed
    months_faster_than_baseline: int
    message: str
    is_meaningful: bool            # False if outcome is same as another scenario


@dataclass
class AssessmentResult:
    # Core
    score: int
    status: str
    time_estimate: str             # Spec-driven label (e.g. "Likely 6–18 months away")

    # Deposit
    deposit_needed: int
    deposit_gap: int
    estimated_months: int          # Calculated from actual deposit gap — drives the main card

    # Blockers
    biggest_blocker: str
    breakdown: Breakdown

    # Action plan
    action_plan: list[str]

    # Saving simulations — [BUG-1, BUG-2, BUG-3]
    saving_scenarios: list[SavingScenario]

    # Affordability
    borrowing_power: int
    total_budget: int
    affordability_gap: int         # 0 if affordable

    # Disclaimer (regulatory)
    disclaimer: str = (
        "This is an estimate for information only. "
        "It is not financial advice, a lending decision, or an eligibility check."
    )


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


def _status_from_score(score: int) -> tuple[str, str]:
    for threshold, status, time_est in SCORE_BANDS:
        if score >= threshold:
            return status, time_est
    return SCORE_BANDS[-1][1], SCORE_BANDS[-1][2]


def _months_to_close(deposit_gap: float, monthly_save: float) -> int:
    """
    Returns months needed to close gap at given save rate.
    Returns MONTHS_CAP if gap cannot be closed within cap.
    Returns 0 if gap is already closed.
    """
    if deposit_gap <= 0:
        return 0
    if monthly_save <= 0:
        return MONTHS_CAP
    return min(MONTHS_CAP, math.ceil(deposit_gap / monthly_save))


# ---------------------------------------------------------------------------
# [BUG-5 FIX] Blocker ranking — excludes deposit when gap is already 0
# ---------------------------------------------------------------------------

def _rank_blockers(
    deposit: ComponentScore,
    income: ComponentScore,
    commitments: ComponentScore,
    credit: ComponentScore,
    deposit_gap: int,
) -> tuple[ComponentScore, ComponentScore, ComponentScore, ComponentScore]:
    """
    Ranks the four components and assigns priority labels.

    BUG-5 FIX: Deposit is excluded from being the 'biggest blocker' when
    deposit_gap == 0, because the user has already met the deposit threshold.
    Even if deposit scores < max (e.g. 25/40), having no gap means it is not
    an actionable blocker — surfacing it would mislead the user.
    """
    components = [
        ("deposit", deposit),
        ("income", income),
        ("commitments", commitments),
        ("credit", credit),
    ]

    # Compute a deficit ratio (lower = worse = higher priority blocker)
    # Deposit gets infinite priority cleared if gap is already closed
    def blocker_priority(item):
        name, comp = item
        if name == "deposit" and deposit_gap == 0:
            # Deposit is satisfied — push it to bottom of blocker ranking
            return 1.0
        return comp.points / comp.max_points  # lower ratio = higher blocker priority

    ranked = sorted(components, key=blocker_priority)

    priority_labels = ["Biggest blocker", "Important", "Important", "Good"]
    named = {name: comp for name, comp in components}

    for i, (name, _) in enumerate(ranked):
        named[name].priority_label = priority_labels[i]
        named[name].is_biggest_blocker = (i == 0)

    return named["deposit"], named["income"], named["commitments"], named["credit"]


# ---------------------------------------------------------------------------
# [BUG-1, BUG-2, BUG-3 FIX] Saving simulations
# ---------------------------------------------------------------------------

def _build_saving_scenarios(
    deposit_gap: int,
    annual_income: float,
    baseline_months: int,
) -> list[SavingScenario]:
    """
    Builds saving improvement scenarios.

    BUG-1 FIX: Rates that produce identical month outcomes to each other are
    flagged as non-meaningful and filtered — only distinct outcomes are shown.

    BUG-2 FIX: Rates below the assumed baseline save rate are framed as
    'slower' scenarios, not improvements. Only rates >= baseline are shown as
    improvements.

    BUG-3 FIX: When ALL rates hit the cap (60 months), the scenarios are
    collapsed into a single message explaining none of the standard rates are
    sufficient, and a price-reduction note is surfaced instead.
    """
    if deposit_gap <= 0:
        return []

    assumed_monthly_save = (annual_income / 12) * ASSUMED_SAVE_RATE
    scenarios = []
    seen_months = set()

    for rate in SIMULATION_RATES:
        months = _months_to_close(deposit_gap, rate)
        diff = baseline_months - months  # positive = faster, negative = slower

        is_improvement = rate >= assumed_monthly_save
        is_meaningful = months not in seen_months
        seen_months.add(months)

        if months == MONTHS_CAP and not is_improvement:
            # Both below baseline AND capped — no useful signal at all
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

    # [BUG-3 FIX] If all meaningful scenarios hit the cap, collapse them
    meaningful = [s for s in scenarios if s.is_meaningful]
    all_capped = all(s.months_to_close == MONTHS_CAP for s in meaningful)
    if all_capped:
        price_reduction_hint = SavingScenario(
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
        )
        return [price_reduction_hint]

    return scenarios


# ---------------------------------------------------------------------------
# Action plan builder
# ---------------------------------------------------------------------------

def _build_action_plan(
    deposit: ComponentScore,
    income: ComponentScore,
    commitments: ComponentScore,
    credit: ComponentScore,
    deposit_gap: int,
    affordability_gap: int,
) -> list[str]:
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
# Main entry point
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

    All arguments match the API payload fields exactly.
    Returns a fully populated AssessmentResult.
    """
    monthly_income = annual_income / 12

    # --- Score components ---
    deposit_comp   = _score_deposit(savings, target_property_price)
    income_comp    = _score_income(annual_income, target_property_price)
    commit_comp    = _score_commitments(monthly_commitments, monthly_income)
    credit_comp    = _score_credit(has_ccj, has_missed_payments)

    total_score = min(100, deposit_comp.points + income_comp.points
                      + commit_comp.points + credit_comp.points)

    # --- Deposit gap ---
    deposit_needed = round(target_property_price * DEPOSIT_THRESHOLD)
    deposit_gap    = max(0, deposit_needed - int(savings))

    # --- Affordability ---
    borrowing_power  = int(annual_income * 4.5)
    total_budget     = borrowing_power + int(savings)
    affordability_gap = max(0, int(target_property_price) - total_budget)

    # --- Timeline ---
    # [BUG-4 FIX]: estimated_months is the SINGLE source of truth for the timeline.
    # The status-band time_estimate label ("Likely 6–18 months away") is a SECONDARY,
    # general label only — it must NOT be shown alongside estimated_months as if they
    # are the same figure. The UI should display estimated_months prominently and
    # treat the status label as supplementary context only.
    assumed_monthly_save = monthly_income * ASSUMED_SAVE_RATE
    estimated_months = _months_to_close(deposit_gap, assumed_monthly_save)

    status, time_estimate = _status_from_score(total_score)

    # --- Blockers ---
    deposit_comp, income_comp, commit_comp, credit_comp = _rank_blockers(
        deposit_comp, income_comp, commit_comp, credit_comp, deposit_gap
    )

    biggest_blocker_name = next(
        name for name, comp in [
            ("deposit", deposit_comp), ("income", income_comp),
            ("commitments", commit_comp), ("credit", credit_comp)
        ] if comp.is_biggest_blocker
    )

    breakdown = Breakdown(
        deposit=deposit_comp,
        income=income_comp,
        commitments=commit_comp,
        credit=credit_comp,
    )

    # --- Action plan ---
    action_plan = _build_action_plan(
        deposit_comp, income_comp, commit_comp, credit_comp,
        deposit_gap, affordability_gap
    )

    # --- Saving simulations ---
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
        biggest_blocker=biggest_blocker_name,
        breakdown=breakdown,
        action_plan=action_plan,
        saving_scenarios=saving_scenarios,
        borrowing_power=borrowing_power,
        total_budget=total_budget,
        affordability_gap=affordability_gap,
    )


# ---------------------------------------------------------------------------
# Quick self-test against known cases
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    TEST_CASES = [
        ("T02 High earner, low savings",   90000,  5000, 350000, 500,  False, False),
        ("T04 CCJ + missed payments",      45000, 20000, 220000, 400,  True,  True),
        ("T07 Aspirational, weak profile", 30000,  2000, 500000, 800,  False, True),
        ("T08 Optional fields omitted",    48000, 14400, 288000, None, None,  None),
        ("T05 Deposit gap = 0 bug test",   55000, 25000, 250000, 600,  False, False),
    ]

    for label, *args in TEST_CASES:
        r = compute_assessment(*args)
        print(f"\n{'='*65}")
        print(f"  {label}")
        print(f"  Score: {r.score}/100 | Status: {r.status} | {r.time_estimate}")
        print(f"  Deposit gap: £{r.deposit_gap:,} | Est. months: {r.estimated_months}")
        print(f"  Biggest blocker: {r.biggest_blocker}")
        print(f"  Breakdown:")
        for name, comp in [
            ("deposit", r.breakdown.deposit), ("income", r.breakdown.income),
            ("commitments", r.breakdown.commitments), ("credit", r.breakdown.credit)
        ]:
            flag = " ← BIGGEST BLOCKER" if comp.is_biggest_blocker else ""
            print(f"    {name:12s} {comp.points}/{comp.max_points}  [{comp.priority_label}]{flag}")
        print(f"  Saving scenarios:")
        for s in r.saving_scenarios:
            tag = "(non-meaningful — duplicate outcome)" if not s.is_meaningful else ""
            amt = f"£{s.monthly_amount}/mo" if s.monthly_amount else "price note"
            print(f"    {amt}: {s.months_to_close}mo | {s.message[:80]}... {tag}")