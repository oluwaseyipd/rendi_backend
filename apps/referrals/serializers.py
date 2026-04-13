from rest_framework import serializers
from .models import Referral


class ReferralStatsSerializer(serializers.ModelSerializer):
    """Returns a user's referral stats and shareable link."""

    referral_url     = serializers.ReadOnlyField()
    conversion_rate  = serializers.ReadOnlyField()

    # Pre-written share text matching the spec copy
    share_text = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            "code",
            "referral_url",
            "invite_count",
            "conversion_count",
            "conversion_rate",
            "share_text",
            "created_at",
        ]
        read_only_fields = fields

    def get_share_text(self, obj) -> str:
        return (
            f"I just checked how close I am to buying a home on Rendi. "
            f"Want to see where you stand? Sign up here: {obj.referral_url}"
        )