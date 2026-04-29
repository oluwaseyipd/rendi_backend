import logging

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Assessment
from .serializers import (
    AssessmentInputSerializer,
    AssessmentResultSerializer,
    AssessmentListSerializer,
)
from .rendi_scoring import compute_assessment, DISCLAIMER

logger = logging.getLogger(__name__)


def _breakdown_component_to_dict(comp):
    """
    Converts a ComponentScore dataclass to a dict for JSON storage.
    The 'value' field has been removed from the new engine — breakdown
    now carries points, max_points, label, priority_label, is_biggest_blocker.
    """
    return {
        "points":             comp.points,
        "max_points":         comp.max_points,
        "label":              comp.label,
        "priority_label":     comp.priority_label,
        "is_biggest_blocker": comp.is_biggest_blocker,
    }


def _scenario_to_dict(scenario):
    """
    Converts a SavingScenario dataclass to a dict for JSON storage.

    Field mapping from old engine → new engine:
      monthly_saving  → monthly_amount
      months_to_goal  → months_to_close
      months_saved    → months_faster_than_baseline
      summary         → message
      label           → (removed, not in new engine)
      is_meaningful   → (new field)
    """
    return {
        "monthly_amount":               scenario.monthly_amount,
        "months_to_close":              scenario.months_to_close,
        "months_faster_than_baseline":  scenario.months_faster_than_baseline,
        "message":                      scenario.message,
        "is_meaningful":                scenario.is_meaningful,
    }


class SubmitAssessmentView(APIView):
    """
    POST /api/assessments/submit/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 1. Validate inputs
        input_serializer = AssessmentInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        # 2. Run scoring engine
        # Note: monthly_saving_ability is accepted by the input serializer
        # for future use but is not consumed by compute_assessment yet.
        result = compute_assessment(
            annual_income=float(data["annual_income"]),
            savings=float(data["savings"]),
            target_property_price=float(data["target_property_price"]),
            monthly_commitments=(
                float(data["monthly_commitments"])
                if data.get("monthly_commitments") is not None
                else None
            ),
            has_ccj=data.get("has_ccj"),
            has_missed_payments=data.get("has_missed_payments"),
        )

        # 3. Get previous score for progress email trigger
        previous = (
            Assessment.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        previous_score = previous.score if previous else None

        # 4. Build blocker_priority list from ranked breakdown components
        # Ordered worst → best so the frontend can render them in priority order.
        breakdown_items = [
            ("deposit",     result.breakdown.deposit),
            ("income",      result.breakdown.income),
            ("commitments", result.breakdown.commitments),
            ("credit",      result.breakdown.credit),
        ]
        blocker_priority = sorted(
            [
                {"component": name, "priority_label": comp.priority_label}
                for name, comp in breakdown_items
            ],
            key=lambda x: (
                0 if x["priority_label"] == "Biggest blocker"
                else 1 if x["priority_label"] == "Important"
                else 2
            ),
        )

        # 5. Persist assessment
        assessment = Assessment.objects.create(
            user=request.user,
            annual_income=data["annual_income"],
            savings=data["savings"],
            target_property_price=data["target_property_price"],
            monthly_commitments=data.get("monthly_commitments"),
            has_ccj=data.get("has_ccj"),
            has_missed_payments=data.get("has_missed_payments"),
            # core outputs
            score=result.score,
            status=result.status,
            time_estimate=result.time_estimate,
            # deposit
            deposit_needed=result.deposit_needed,
            deposit_gap=result.deposit_gap,
            estimated_months=result.estimated_months,
            # breakdown
            breakdown={
                "deposit":     _breakdown_component_to_dict(result.breakdown.deposit),
                "income":      _breakdown_component_to_dict(result.breakdown.income),
                "commitments": _breakdown_component_to_dict(result.breakdown.commitments),
                "credit":      _breakdown_component_to_dict(result.breakdown.credit),
            },
            # blockers
            biggest_blocker=result.biggest_blocker,
            blocker_priority=blocker_priority,
            # plan & simulations
            action_plan=result.action_plan,
            recommendations=result.action_plan,  # kept in sync for backwards compat
            simulations=[_scenario_to_dict(s) for s in result.saving_scenarios],
            # affordability
            borrowing_power=result.borrowing_power,
            total_budget=result.total_budget,
            affordability_gap=result.affordability_gap,
        )

        # 6. Fire email tasks asynchronously
        try:
            from apps.emails.tasks import (
                send_post_assessment_emails_task,
                send_progress_email_task,
            )
            if previous_score is not None and result.score > previous_score:
                send_progress_email_task.delay(
                    request.user.pk, assessment.pk, previous_score
                )
            else:
                send_post_assessment_emails_task.delay(
                    request.user.pk, assessment.pk
                )
        except Exception as exc:
            logger.error("Email task dispatch failed: %s", exc)

        # 7. Return result
        return Response(
            {
                "disclaimer": result.disclaimer,
                "assessment": AssessmentResultSerializer(assessment).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LatestAssessmentView(APIView):
    """
    GET /api/assessments/latest/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        assessment = Assessment.objects.filter(user=request.user).first()
        if not assessment:
            return Response(
                {"detail": "No assessments found. Submit one to get started."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "disclaimer": DISCLAIMER,
                "assessment": AssessmentResultSerializer(assessment).data,
            }
        )


class AssessmentHistoryView(generics.ListAPIView):
    """
    GET /api/assessments/history/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssessmentListSerializer

    def get_queryset(self):
        return Assessment.objects.filter(user=self.request.user)


class AssessmentDetailView(generics.RetrieveAPIView):
    """
    GET /api/assessments/<id>/
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssessmentResultSerializer

    def get_queryset(self):
        return Assessment.objects.filter(user=self.request.user)


class ComparisonView(APIView):
    """
    GET /api/assessments/compare/
    Returns "How you compare" data for the user's latest assessment.
    Falls back gracefully when there isn't enough data yet.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        assessment = Assessment.objects.filter(user=request.user).first()
        if not assessment:
            return Response(
                {"detail": "Complete an assessment first to see how you compare."},
                status=status.HTTP_404_NOT_FOUND,
            )

        from .comparison import calculate_comparison
        result = calculate_comparison(assessment)

        return Response({
            "has_data":          result.has_data,
            "fallback_message":  result.fallback_message,
            "headline":          result.headline,
            "headline_pct":      result.headline_pct,
            "subtitle":          result.subtitle,
            "savings_line":      result.savings_line,
            "deposit_gap_line":  result.deposit_gap_line,
            "segment_label":     result.segment_label,
            "total_users":       result.total_users,
            "share_text":        result.share_text,
        })