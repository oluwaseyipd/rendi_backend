from django.contrib import admin
from .models import Referral, ReferralConversion


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display  = ("user", "code", "invite_count", "conversion_count", "conversion_rate", "created_at")
    search_fields = ("user__email", "code")
    ordering      = ("-created_at",)
    readonly_fields = (
        "user", "code", "invite_count", "conversion_count",
        "referral_url", "conversion_rate", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(ReferralConversion)
class ReferralConversionAdmin(admin.ModelAdmin):
    list_display  = ("referral", "referred_user", "converted_at")
    search_fields = ("referral__user__email", "referred_user__email")
    ordering      = ("-converted_at",)
    readonly_fields = ("referral", "referred_user", "converted_at")

    def has_add_permission(self, request):
        return False