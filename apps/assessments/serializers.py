from rest_framework import serializers
from .models import Assessment


class AssessmentInputSerializer(serializers.Serializer):
    """
    Validates the user-submitted assessment form data.
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

    # Phase 1: optional declared saving ability
    monthly_saving_ability = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0,
        required=False, allow_null=True
    )


class SimulationSerializer(serializers.Serializer):
    """Serializes a single savings simulation scenario."""
    monthly_saving = serializers.IntegerField()
    months_to_goal = serializers.IntegerField()
    months_saved   = serializers.IntegerField()
    label          = serializers.CharField()
    summary        = serializers.CharField()


class ComponentBreakdownSerializer(serializers.Serializer):
    """Serializes a single scoring component's breakdown."""
    points     = serializers.IntegerField()
    max_points = serializers.IntegerField()
    label      = serializers.CharField()
    value      = serializers.FloatField()


class AssessmentResultSerializer(serializers.ModelSerializer):
    """
    Full assessment result — returned after submit or when fetching detail/latest.
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
            # core outputs
            "score",
            "status",
            "time_estimate",
            # deposit helpers
            "deposit_needed",
            "deposit_gap",
            "estimated_months",
            # breakdown
            "breakdown",
            # Phase 1 new fields
            "biggest_blocker",
            "blocker_priority",
            "recommendations",
            "simulations",
            # legacy
            "action_plan",
            # meta
            "created_at",
        ]
        read_only_fields = fields


class AssessmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the history list.
    Includes biggest_blocker so the history page can show context
    without loading the full breakdown.
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
            "biggest_blocker",
            "created_at",
        ]
        read_only_fields = fields