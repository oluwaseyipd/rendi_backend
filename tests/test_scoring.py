"""
tests/test_scoring.py
---------------------
Unit tests for the Rendi scoring engine.
Run with: python manage.py test tests
"""

from django.test import TestCase
from apps.assessments.rendi_scoring import ScoringInputs, calculate_readiness


class DepositScoringTests(TestCase):

    def _score(self, savings, price):
        return calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=savings,
            target_property_price=price,
        ))

    def test_deposit_under_5_percent_scores_0(self):
        result = self._score(savings=4000, price=200000)   # 2%
        self.assertEqual(result.deposit_breakdown.points, 0)
        self.assertEqual(result.deposit_breakdown.label, "Needs attention")

    def test_deposit_5_to_9_percent_scores_15(self):
        result = self._score(savings=10000, price=200000)  # 5%
        self.assertEqual(result.deposit_breakdown.points, 15)

    def test_deposit_10_to_14_percent_scores_25(self):
        result = self._score(savings=20000, price=200000)  # 10%
        self.assertEqual(result.deposit_breakdown.points, 25)

    def test_deposit_15_percent_plus_scores_40(self):
        result = self._score(savings=30000, price=200000)  # 15%
        self.assertEqual(result.deposit_breakdown.points, 40)
        self.assertEqual(result.deposit_breakdown.label, "Strong")


class IncomeScoringTests(TestCase):

    def _score(self, income, price):
        return calculate_readiness(ScoringInputs(
            annual_income=income,
            savings=20000,
            target_property_price=price,
        ))

    def test_income_multiple_over_5x_scores_5(self):
        result = self._score(income=40000, price=250000)   # 6.25x
        self.assertEqual(result.income_breakdown.points, 5)
        self.assertEqual(result.income_breakdown.label, "Needs attention")

    def test_income_multiple_4_1_to_5x_scores_15(self):
        result = self._score(income=50000, price=225000)   # 4.5x
        self.assertEqual(result.income_breakdown.points, 15)

    def test_income_multiple_3_1_to_4x_scores_25(self):
        result = self._score(income=60000, price=210000)   # 3.5x
        self.assertEqual(result.income_breakdown.points, 25)

    def test_income_multiple_3x_or_less_scores_30(self):
        result = self._score(income=80000, price=200000)   # 2.5x
        self.assertEqual(result.income_breakdown.points, 30)
        self.assertEqual(result.income_breakdown.label, "Strong")


class CommitmentsScoringTests(TestCase):

    def _score(self, monthly_commitments):
        return calculate_readiness(ScoringInputs(
            annual_income=48000,          # £4,000/month
            savings=20000,
            target_property_price=200000,
            monthly_commitments=monthly_commitments,
        ))

    def test_no_commitments_provided_scores_10_neutral(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=48000,
            savings=20000,
            target_property_price=200000,
            monthly_commitments=None,
        ))
        self.assertEqual(result.commitments_breakdown.points, 10)
        self.assertEqual(result.commitments_breakdown.label, "Not provided")

    def test_commitments_under_10_percent_scores_20(self):
        result = self._score(monthly_commitments=300)   # 7.5% of £4k
        self.assertEqual(result.commitments_breakdown.points, 20)
        self.assertEqual(result.commitments_breakdown.label, "Low impact")

    def test_commitments_11_to_25_percent_scores_15(self):
        result = self._score(monthly_commitments=700)   # 17.5%
        self.assertEqual(result.commitments_breakdown.points, 15)

    def test_commitments_26_to_40_percent_scores_10(self):
        result = self._score(monthly_commitments=1300)  # 32.5%
        self.assertEqual(result.commitments_breakdown.points, 10)

    def test_commitments_over_40_percent_scores_0(self):
        result = self._score(monthly_commitments=2000)  # 50%
        self.assertEqual(result.commitments_breakdown.points, 0)
        self.assertEqual(result.commitments_breakdown.label, "Needs attention")


class CreditScoringTests(TestCase):

    def _base(self, **kwargs):
        return calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=20000,
            target_property_price=200000,
            **kwargs,
        ))

    def test_ccj_yes_scores_0(self):
        result = self._base(has_ccj=True)
        self.assertEqual(result.credit_breakdown.points, 0)
        self.assertEqual(result.credit_breakdown.label, "Needs attention")

    def test_missed_payments_no_ccj_scores_5(self):
        result = self._base(has_ccj=False, has_missed_payments=True)
        self.assertEqual(result.credit_breakdown.points, 5)
        self.assertEqual(result.credit_breakdown.label, "Okay")

    def test_no_issues_scores_10(self):
        result = self._base(has_ccj=False, has_missed_payments=False)
        self.assertEqual(result.credit_breakdown.points, 10)
        self.assertEqual(result.credit_breakdown.label, "Low impact")

    def test_both_skipped_scores_5_neutral(self):
        result = self._base(has_ccj=None, has_missed_payments=None)
        self.assertEqual(result.credit_breakdown.points, 5)
        self.assertEqual(result.credit_breakdown.label, "Not provided")


class StatusThresholdTests(TestCase):

    def test_score_below_40_is_early_stages(self):
        # Very weak profile
        result = calculate_readiness(ScoringInputs(
            annual_income=20000,
            savings=1000,
            target_property_price=500000,
            monthly_commitments=2000,
            has_ccj=True,
        ))
        self.assertEqual(result.status, "Early stages")
        self.assertIn("18–36 months", result.time_estimate)

    def test_score_40_to_69_is_getting_closer(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=45000,
            savings=18000,
            target_property_price=220000,
            monthly_commitments=500,
            has_ccj=False,
            has_missed_payments=False,
        ))
        self.assertIn(result.status, ("Getting closer", "Nearly ready"))

    def test_score_70_plus_is_nearly_ready(self):
        # Strong profile
        result = calculate_readiness(ScoringInputs(
            annual_income=80000,
            savings=40000,
            target_property_price=200000,
            monthly_commitments=200,
            has_ccj=False,
            has_missed_payments=False,
        ))
        self.assertEqual(result.status, "Nearly ready")
        self.assertIn("0–6 months", result.time_estimate)

    def test_score_clamped_to_100(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=200000,
            savings=500000,
            target_property_price=200000,
            monthly_commitments=0,
            has_ccj=False,
            has_missed_payments=False,
        ))
        self.assertLessEqual(result.score, 100)

    def test_score_clamped_to_0(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=0,
            savings=0,
            target_property_price=1000000,
            monthly_commitments=99999,
            has_ccj=True,
        ))
        self.assertGreaterEqual(result.score, 0)


class DepositHelperTests(TestCase):

    def test_deposit_needed_is_10_percent(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=5000,
            target_property_price=300000,
        ))
        self.assertEqual(result.deposit_needed, 30000)

    def test_deposit_gap_when_savings_short(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=5000,
            target_property_price=300000,
        ))
        self.assertEqual(result.deposit_gap, 25000)

    def test_deposit_gap_zero_when_savings_meet_benchmark(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=30000,
            target_property_price=300000,
        ))
        self.assertEqual(result.deposit_gap, 0)
        self.assertEqual(result.estimated_months, 0)

    def test_estimated_months_capped_at_60(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=10000,
            savings=0,
            target_property_price=1000000,
        ))
        self.assertLessEqual(result.estimated_months, 60)


class DisclaimerTests(TestCase):

    def test_disclaimer_always_present(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=20000,
            target_property_price=200000,
        ))
        self.assertIn("estimate", result.disclaimer.lower())
        self.assertIn("not financial advice", result.disclaimer.lower())

    def test_action_plan_always_ends_with_revisit_message(self):
        result = calculate_readiness(ScoringInputs(
            annual_income=50000,
            savings=20000,
            target_property_price=200000,
        ))
        self.assertTrue(
            any("revisit" in item.lower() for item in result.action_plan)
        )
