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
from .rendi_scoring import ScoringInputs, calculate_readiness

logger = logging.getLogger(__name__)


def _breakdown_to_dict(breakdown):
    return {
        "points":     breakdown.points,
        "max_points": breakdown.max_points,
        "label":      breakdown.label,
        "value":      breakdown.value,
    }


def _simulation_to_dict(sim):
    return {
        "monthly_saving": sim.monthly_saving,
        "months_to_goal": sim.months_to_goal,
        "months_saved":   sim.months_saved,
        "label":          sim.label,
        "summary":        sim.summary,
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
        scoring_inputs = ScoringInputs(
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
            monthly_saving_ability=(
                float(data["monthly_saving_ability"])
                if data.get("monthly_saving_ability") is not None
                else None
            ),
        )
        result = calculate_readiness(scoring_inputs)

        # 3. Get previous score for progress email trigger
        previous = (
            Assessment.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        previous_score = previous.score if previous else None

        # 4. Persist assessment
        assessment = Assessment.objects.create(
            user=request.user,
            annual_income=data["annual_income"],
            savings=data["savings"],
            target_property_price=data["target_property_price"],
            monthly_commitments=data.get("monthly_commitments"),
            has_ccj=data.get("has_ccj"),
            has_missed_payments=data.get("has_missed_payments"),
            score=result.score,
            status=result.status,
            time_estimate=result.time_estimate,
            deposit_needed=result.deposit_needed,
            deposit_gap=result.deposit_gap,
            estimated_months=result.estimated_months,
            breakdown={
                "deposit":     _breakdown_to_dict(result.deposit_breakdown),
                "income":      _breakdown_to_dict(result.income_breakdown),
                "commitments": _breakdown_to_dict(result.commitments_breakdown),
                "credit":      _breakdown_to_dict(result.credit_breakdown),
            },
            biggest_blocker=result.biggest_blocker,
            blocker_priority=result.blocker_priority,
            recommendations=result.recommendations,
            simulations=[_simulation_to_dict(s) for s in result.simulations],
            action_plan=result.action_plan,
        )

        # 5. Fire email tasks asynchronously
        try:
            from apps.emails.tasks import (
                send_post_assessment_emails_task,
                send_progress_email_task,
            )
            if previous_score is not None and result.score > previous_score:
                # Returning user with score improvement — send progress email
                send_progress_email_task.delay(
                    request.user.pk, assessment.pk, previous_score
                )
            else:
                # New submission — send full post-assessment suite
                send_post_assessment_emails_task.delay(
                    request.user.pk, assessment.pk
                )
        except Exception as exc:
            # Never let email failures break the API response
            logger.error("Email task dispatch failed: %s", exc)

        # 6. Return result
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

        from .rendi_scoring import DISCLAIMER
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
            "has_data":        result.has_data,
            "fallback_message": result.fallback_message,
            "headline":        result.headline,
            "headline_pct":    result.headline_pct,
            "subtitle":        result.subtitle,
            "savings_line":    result.savings_line,
            "deposit_gap_line": result.deposit_gap_line,
            "segment_label":   result.segment_label,
            "total_users":     result.total_users,
            "share_text":      result.share_text,
        })
