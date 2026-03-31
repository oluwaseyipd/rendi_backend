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


def _breakdown_to_dict(breakdown):
    """Converts a ComponentBreakdown dataclass to a plain dict for JSON storage."""
    return {
        "points": breakdown.points,
        "max_points": breakdown.max_points,
        "label": breakdown.label,
        "value": breakdown.value,
    }


class SubmitAssessmentView(APIView):
    """
    POST /api/assessments/submit/

    Accepts user inputs, runs the scoring engine, persists the result,
    and returns the full scored assessment.

    Requires: Bearer token authentication.
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
        )
        result = calculate_readiness(scoring_inputs)

        # 3. Persist assessment record
        assessment = Assessment.objects.create(
            user=request.user,
            # inputs
            annual_income=data["annual_income"],
            savings=data["savings"],
            target_property_price=data["target_property_price"],
            monthly_commitments=data.get("monthly_commitments"),
            has_ccj=data.get("has_ccj"),
            has_missed_payments=data.get("has_missed_payments"),
            # outputs
            score=result.score,
            status=result.status,
            time_estimate=result.time_estimate,
            deposit_needed=result.deposit_needed,
            deposit_gap=result.deposit_gap,
            estimated_months=result.estimated_months,
            breakdown={
                "deposit": _breakdown_to_dict(result.deposit_breakdown),
                "income": _breakdown_to_dict(result.income_breakdown),
                "commitments": _breakdown_to_dict(result.commitments_breakdown),
                "credit": _breakdown_to_dict(result.credit_breakdown),
            },
            action_plan=result.action_plan,
        )

        # 4. Return full result
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

    Returns the most recent assessment for the authenticated user.
    Returns 404 if the user has no assessments yet.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        assessment = (
            Assessment.objects.filter(user=request.user).first()
        )
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

    Returns a paginated list of all past assessments for the authenticated user,
    ordered newest first. Uses the lightweight list serializer.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssessmentListSerializer

    def get_queryset(self):
        return Assessment.objects.filter(user=self.request.user)


class AssessmentDetailView(generics.RetrieveAPIView):
    """
    GET /api/assessments/<id>/

    Returns full detail for a single assessment belonging to the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssessmentResultSerializer

    def get_queryset(self):
        return Assessment.objects.filter(user=self.request.user)
