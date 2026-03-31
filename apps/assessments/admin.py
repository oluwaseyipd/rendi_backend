from django.contrib import admin
from .models import Assessment


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "score",
        "status",
        "target_property_price",
        "deposit_gap",
        "estimated_months",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("user__email",)
    ordering = ("-created_at",)
    readonly_fields = (
        "user",
        "annual_income",
        "savings",
        "target_property_price",
        "monthly_commitments",
        "has_ccj",
        "has_missed_payments",
        "score",
        "status",
        "time_estimate",
        "deposit_needed",
        "deposit_gap",
        "estimated_months",
        "breakdown",
        "action_plan",
        "created_at",
    )

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Inputs",
            {
                "fields": (
                    "annual_income",
                    "savings",
                    "target_property_price",
                    "monthly_commitments",
                    "has_ccj",
                    "has_missed_payments",
                )
            },
        ),
        (
            "Result",
            {
                "fields": (
                    "score",
                    "status",
                    "time_estimate",
                    "deposit_needed",
                    "deposit_gap",
                    "estimated_months",
                )
            },
        ),
        ("Breakdown & Action Plan", {"fields": ("breakdown", "action_plan")}),
        ("Meta", {"fields": ("created_at",)}),
    )

    # Assessments are immutable records — disable add/delete from admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
