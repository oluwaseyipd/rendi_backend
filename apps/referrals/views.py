import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Referral
from .serializers import ReferralStatsSerializer

logger = logging.getLogger(__name__)


class GenerateReferralView(APIView):
    """
    POST /api/referrals/generate/

    Creates a Referral record for the authenticated user if one doesn't
    exist yet, then returns their referral stats and shareable link.
    Safe to call multiple times — idempotent.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        referral, created = Referral.objects.get_or_create(user=request.user)
        return Response(
            ReferralStatsSerializer(referral).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReferralStatsView(APIView):
    """
    GET /api/referrals/stats/

    Returns the authenticated user's referral stats.
    Returns 404 if they haven't generated a referral link yet.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            referral = Referral.objects.get(user=request.user)
        except Referral.DoesNotExist:
            # Auto-create so the frontend never has to handle 404 here
            referral = Referral.objects.create(user=request.user)

        return Response(ReferralStatsSerializer(referral).data)