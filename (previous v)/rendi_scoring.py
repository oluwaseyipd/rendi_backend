"""
rendi_scoring.py
----------------
Deterministic readiness scoring engine for Rendi MVP.
Phase 1 upgrade — aligned with:
  - Rendi Backend Recommendation Engine spec (doc 1)
  - Rendi CTO Product Upgrade document (doc 2)

Changes in this version:
  - Stage bands updated to 0-34 / 35-64 / 65-84 / 85+
  - Biggest-blocker ranking added
  - Quantified personalised recommendations (pound amounts)
  - Fastest-improvement simulation engine (300 / 500 / 750/month)

All outputs are INFORMATIONAL ESTIMATES ONLY.
This is not financial advice, a lending decision, or an eligibility check.
"""

from dataclasses import dataclass, field
from typing import Optional


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class ScoringInputs:
    annual_income: float
    savings: float
    target_property_price: float
    monthly_commitments: Optional[float] = None
    has_ccj: Optional[bool] = None
    has_missed_payments: Optional[bool] = None
    monthly_saving_ability: Optional[float] = None


@dataclass
class ComponentBreakdown:
    points: int
    max_points: int
    label: str
    value: float
    deficit: int = field(init=False)

    def __post_init__(self):
        self.deficit = self.max_points - self.points


@dataclass
class Simulation:
    monthly_saving: int
    months_to_goal: int
    months_saved: int
    label: str
    summary: str


@dataclass
class ScoringResult:
    score: int
    status: str
    time_estimate: str

    deposit_breakdown: ComponentBreakdown
    income_breakdown: ComponentBreakdown
    commitments_breakdown: ComponentBreakdown
    credit_breakdown: ComponentBreakdown

    biggest_blocker: str
    blocker_priority: list

    deposit_needed: float
    deposit_gap: float
    estimated_months: int

    recommendations: list
    simulations: list
    action_plan: list

    disclaimer: str


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DEPOSIT_BENCHMARK_PERCENT = 0.10
ASSUMED_SAVINGS_RATE = 0.15
MAX_ESTIMATED_MONTHS = 60

STATUS_THRESHOLDS = {
    "strong_position":   85,
    "getting_close":     65,
    "building_momentum": 35,
}

STATUS_LABELS = {
    "strong_position":   "Strong position",
    "getting_close":     "Getting close",
    "building_momentum": "Building momentum",
    "early_stages":      "Early stages",
}

TIME_ESTIMATES = {
    "Strong position":   "Likely 0-6 months away",
    "Getting close":     "Likely 6-12 months away",
    "Building momentum": "Likely 12-18 months away",
    "Early stages":      "Likely 18-36 months away",
}

SIMULATION_SCENARIOS = [300, 500, 750]

DISCLAIMER = (
    "This is an estimate for information only. It is not financial advice, "
    "a mortgage offer, or an eligibility decision."
)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def _ceiling_divide(numerator, denominator):
    return int(-(-numerator // denominator))


# ------------------------------------------------------------------
# Component scorers
# ------------------------------------------------------------------

def _score_deposit(savings, price):
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
        value=round(deposit_percent * 100, 2),
    )


def _score_income(income, price):
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


def _score_commitments(monthly_commitments, monthly_income):
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


def _score_credit(has_ccj, has_missed_payments):
    if has_ccj is None and has_missed_payments is None:
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
        value=-1,
    )


# ------------------------------------------------------------------
# Biggest-blocker ranker
# ------------------------------------------------------------------

def _rank_blockers(deposit_bd, income_bd, commitments_bd, credit_bd):
    components = {
        "deposit":     deposit_bd,
        "income":      income_bd,
        "commitments": commitments_bd,
        "credit":      credit_bd,
    }
    ranked = sorted(
        components.items(),
        key=lambda x: x[1].deficit,
        reverse=True,
    )
    ordered_keys = [k for k, _ in ranked]
    return ordered_keys[0], ordered_keys


# ------------------------------------------------------------------
# Quantified recommendation builder
# ------------------------------------------------------------------

def _build_recommendations(
    inputs_income,
    inputs_savings,
    inputs_price,
    inputs_monthly_commitments,
    deposit_bd,
    income_bd,
    commitments_bd,
    credit_bd,
    deposit_gap,
    blocker_priority,
):
    recs = []
    monthly_income = inputs_income / 12

    for key in blocker_priority:

        if key == "deposit" and deposit_bd.label in ("Needs attention", "Getting there"):
            if deposit_gap > 0:
                target_months = 36
                monthly_needed = max(1, round(deposit_gap / target_months / 10) * 10)
                recs.append(
                    "Increase your deposit by £{:,} to reach the 10% benchmark. "
                    "Saving around £{:,}/month would get you there in approximately "
                    "{} months.".format(int(deposit_gap), int(monthly_needed), target_months)
                )
            else:
                recs.append(
                    "Your deposit is above the 10% benchmark — consider saving toward 15% "
                    "to access better mortgage rates."
                )

        elif key == "income" and income_bd.label == "Needs attention":
            target_multiple = 4.5
            affordable_price = round(inputs_income * target_multiple / 1000) * 1000
            price_reduction = round((inputs_price - affordable_price) / 1000) * 1000
            if price_reduction > 0:
                recs.append(
                    "Your target price is {:.1f}x your income. "
                    "Reducing your target by £{:,} to around £{:,} "
                    "would bring you within a more typical lending range.".format(
                        income_bd.value, int(price_reduction), int(affordable_price)
                    )
                )
            else:
                recs.append(
                    "Consider reviewing your target property price relative to your income "
                    "to improve your affordability picture."
                )

        elif key == "commitments" and commitments_bd.label == "Needs attention":
            if inputs_monthly_commitments and monthly_income > 0:
                target_ratio = 0.25
                target_monthly = monthly_income * target_ratio
                reduction_needed = round((inputs_monthly_commitments - target_monthly) / 10) * 10
                if reduction_needed > 0:
                    recs.append(
                        "Your monthly commitments are £{:,}/month ({:.0f}% of your income). "
                        "Reducing them by approximately £{:,}/month would move you into "
                        "a better affordability range.".format(
                            int(inputs_monthly_commitments),
                            commitments_bd.value,
                            int(reduction_needed),
                        )
                    )
                else:
                    recs.append(
                        "Consider reducing existing debt balances to improve your monthly affordability."
                    )
            else:
                recs.append(
                    "Consider reducing existing debt balances or outgoings to improve "
                    "your affordability picture."
                )

        elif key == "credit" and credit_bd.label == "Needs attention":
            recs.append(
                "A County Court Judgement (CCJ) on your record can significantly affect "
                "mortgage applications. Consider seeking independent advice on resolving it, "
                "and ensure all other payments are kept up to date."
            )

    recs.append("You can revisit this estimate as your situation changes.")
    return recs


# ------------------------------------------------------------------
# Fastest-improvement simulator
# ------------------------------------------------------------------

def _build_simulations(deposit_gap, baseline_months, monthly_income, monthly_saving_ability):
    if deposit_gap <= 0:
        return []

    simulations = []

    for scenario_amount in SIMULATION_SCENARIOS:
        if scenario_amount <= 0:
            continue

        months = _ceiling_divide(deposit_gap, scenario_amount)
        months = int(_clamp(months, 0, MAX_ESTIMATED_MONTHS))
        months_saved = max(0, baseline_months - months)

        if months < baseline_months:
            summary = (
                "If you save £{:,}/month, you could reach your deposit "
                "goal in {} months instead of {} — "
                "that's {} months faster.".format(
                    scenario_amount, months, baseline_months, months_saved
                )
            )
        elif months == baseline_months:
            summary = (
                "Saving £{:,}/month keeps you on the same timeline "
                "of approximately {} months.".format(scenario_amount, months)
            )
        else:
            summary = (
                "Saving £{:,}/month would take approximately "
                "{} months to close your deposit gap.".format(scenario_amount, months)
            )

        simulations.append(
            Simulation(
                monthly_saving=scenario_amount,
                months_to_goal=months,
                months_saved=months_saved,
                label="Save £{:,}/month".format(scenario_amount),
                summary=summary,
            )
        )

    return simulations


# ------------------------------------------------------------------
# Legacy action plan (kept for backwards compatibility)
# ------------------------------------------------------------------

def _build_action_plan(deposit_bd, income_bd, commitments_bd, credit_bd):
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

def calculate_readiness(inputs):
    income  = max(0.0, inputs.annual_income)
    savings = max(0.0, inputs.savings)
    price   = max(1.0, inputs.target_property_price)
    monthly_income = income / 12

    deposit_bd     = _score_deposit(savings, price)
    income_bd      = _score_income(income, price)
    commitments_bd = _score_commitments(inputs.monthly_commitments, monthly_income)
    credit_bd      = _score_credit(inputs.has_ccj, inputs.has_missed_payments)

    raw_score = (
        deposit_bd.points
        + income_bd.points
        + commitments_bd.points
        + credit_bd.points
    )
    score = int(_clamp(raw_score, 0, 100))

    if score >= STATUS_THRESHOLDS["strong_position"]:
        status = STATUS_LABELS["strong_position"]
    elif score >= STATUS_THRESHOLDS["getting_close"]:
        status = STATUS_LABELS["getting_close"]
    elif score >= STATUS_THRESHOLDS["building_momentum"]:
        status = STATUS_LABELS["building_momentum"]
    else:
        status = STATUS_LABELS["early_stages"]

    time_estimate = TIME_ESTIMATES[status]

    deposit_needed = round(price * DEPOSIT_BENCHMARK_PERCENT)
    deposit_gap    = round(max(0.0, deposit_needed - savings))

    if inputs.monthly_saving_ability and inputs.monthly_saving_ability > 0:
        assumed_monthly_save = inputs.monthly_saving_ability
    else:
        assumed_monthly_save = max(0.0, monthly_income * ASSUMED_SAVINGS_RATE)

    if deposit_gap > 0 and assumed_monthly_save > 0:
        estimated_months = int(_clamp(
            _ceiling_divide(deposit_gap, assumed_monthly_save),
            0, MAX_ESTIMATED_MONTHS
        ))
    elif deposit_gap > 0:
        estimated_months = MAX_ESTIMATED_MONTHS
    else:
        estimated_months = 0

    biggest_blocker, blocker_priority = _rank_blockers(
        deposit_bd, income_bd, commitments_bd, credit_bd
    )

    recommendations = _build_recommendations(
        inputs_income=income,
        inputs_savings=savings,
        inputs_price=price,
        inputs_monthly_commitments=inputs.monthly_commitments,
        deposit_bd=deposit_bd,
        income_bd=income_bd,
        commitments_bd=commitments_bd,
        credit_bd=credit_bd,
        deposit_gap=deposit_gap,
        blocker_priority=blocker_priority,
    )

    simulations = _build_simulations(
        deposit_gap=deposit_gap,
        baseline_months=estimated_months,
        monthly_income=monthly_income,
        monthly_saving_ability=inputs.monthly_saving_ability,
    )

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
        biggest_blocker=biggest_blocker,
        blocker_priority=blocker_priority,
        deposit_needed=deposit_needed,
        deposit_gap=deposit_gap,
        estimated_months=estimated_months,
        recommendations=recommendations,
        simulations=simulations,
        action_plan=action_plan,
        disclaimer=DISCLAIMER,
    )