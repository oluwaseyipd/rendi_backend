from rest_framework import serializers
from .models import Assessment


class AssessmentInputSerializer(serializers.Serializer):
    """
    Validates the user-submitted assessment form data.
    monthly_saving_ability is accepted for future use but is not yet
    consumed by the scoring engine.
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
        required=False, allow_null=True,
    )
    has_ccj = serializers.BooleanField(required=False, allow_null=True)
    has_missed_payments = serializers.BooleanField(required=False, allow_null=True)
    monthly_saving_ability = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0,
        required=False, allow_null=True,
    )


class SavingScenarioSerializer(serializers.Serializer):
    """
    Serializes a single saving improvement scenario.

    Field changes from old SimulationSerializer:
      monthly_saving  → monthly_amount
      months_to_goal  → months_to_close
      months_saved    → months_faster_than_baseline
      summary         → message
      label           → removed (not in new engine)
      is_meaningful   → added (new — lets frontend suppress duplicate outcomes)
    """
    monthly_amount               = serializers.IntegerField()
    months_to_close              = serializers.IntegerField()
    months_faster_than_baseline  = serializers.IntegerField()
    message                      = serializers.CharField()
    is_meaningful                = serializers.BooleanField()


class ComponentBreakdownSerializer(serializers.Serializer):
    """
    Serializes a single scoring component's breakdown.

    Field changes from old ComponentBreakdownSerializer:
      value          → removed (deposit_pct / income_multiple no longer exposed here)
      priority_label → added  (e.g. "Biggest blocker" | "Important" | "Good")
      is_biggest_blocker → added
    """
    points             = serializers.IntegerField()
    max_points         = serializers.IntegerField()
    label              = serializers.CharField()
    priority_label     = serializers.CharField()
    is_biggest_blocker = serializers.BooleanField()


class AssessmentResultSerializer(serializers.ModelSerializer):
    """
    Full assessment result — returned after submit and for detail/latest views.

    New fields added:
      biggest_blocker, blocker_priority, borrowing_power,
      total_budget, affordability_gap, simulations (renamed from old shape).

    breakdown is stored as JSON on the model and returned as-is;
    its internal shape now matches ComponentBreakdownSerializer.
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
            # deposit
            "deposit_needed",
            "deposit_gap",
            "estimated_months",
            # breakdown (JSON field — shape defined by ComponentBreakdownSerializer)
            "breakdown",
            # blockers
            "biggest_blocker",
            "blocker_priority",
            # plan & simulations
            "action_plan",
            "recommendations",
            "simulations",
            # affordability
            "borrowing_power",
            "total_budget",
            "affordability_gap",
            # meta
            "created_at",
        ]
        read_only_fields = fields


class AssessmentListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the history list.
    No breakdown — keeps the list response fast and small.
    biggest_blocker included so the history page can show context per entry.
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