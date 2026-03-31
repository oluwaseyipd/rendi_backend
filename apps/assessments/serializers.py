from rest_framework import serializers
from .models import Assessment


class AssessmentInputSerializer(serializers.Serializer):
    """
    Validates the user-submitted assessment form data.
    Only these fields come in from the frontend.
    """
    annual_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0
    )
    savings = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0
    )
    target_property_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=1
    )
    monthly_commitments = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0,
        required=False, allow_null=True
    )
    has_ccj = serializers.BooleanField(required=False, allow_null=True)
    has_missed_payments = serializers.BooleanField(required=False, allow_null=True)


class ComponentBreakdownSerializer(serializers.Serializer):
    """Serializes a single scoring component's breakdown."""
    points = serializers.IntegerField()
    max_points = serializers.IntegerField()
    label = serializers.CharField()
    value = serializers.FloatField()


class AssessmentResultSerializer(serializers.ModelSerializer):
    """
    Full assessment result — returned after submit or when fetching history.
    """

    class Meta:
        model = Assessment
        fields = [
            "id",
            # inputs
            "annual_income",
            "savings",
            "target_property_price",
            "monthly_commitments",
            "has_ccj",
            "has_missed_payments",
            # outputs
            "score",
            "status",
            "time_estimate",
            "deposit_needed",
            "deposit_gap",
            "estimated_months",
            "breakdown",
            "action_plan",
            # meta
            "created_at",
        ]
        read_only_fields = fields


class AssessmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the history list — omits verbose breakdown.
    """

    class Meta:
        model = Assessment
        fields = [
            "id",
            "score",
            "status",
            "time_estimate",
            "target_property_price",
            "deposit_gap",
            "estimated_months",
            "created_at",
        ]
        read_only_fields = fields
