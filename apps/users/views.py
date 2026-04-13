import logging

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    RegisterSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
)

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/

    Creates a new user account.
    Accepts an optional ?ref=<code> query param to track referral conversions.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Phase 4: detect referral code from query param or request body
        # Frontend passes it as ?ref=<code> on the registration URL
        ref_code = (
            request.query_params.get("ref")
            or request.data.get("referral_code")
        )
        if ref_code:
            try:
                from apps.referrals.models import Referral, ReferralConversion
                referral = Referral.objects.get(code=ref_code)

                # Record the conversion
                ReferralConversion.objects.create(
                    referral=referral,
                    referred_user=user,
                )

                # Increment counters
                referral.invite_count     = referral.invite_count + 1
                referral.conversion_count = referral.conversion_count + 1
                referral.save(update_fields=["invite_count", "conversion_count", "updated_at"])

                logger.info(
                    "Referral conversion recorded | referrer=%s | new_user=%s",
                    referral.user.email,
                    user.email,
                )
            except Exception as exc:
                # Never let referral tracking break registration
                logger.error("Referral tracking failed: %s", exc)

        # Phase 3: fire welcome email asynchronously
        try:
            from apps.emails.tasks import send_welcome_email_task
            send_welcome_email_task.delay(user.pk)
        except Exception as exc:
            logger.error("Welcome email task failed for user %s: %s", user.pk, exc)

        return Response(
            {
                "message": "Account created successfully.",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Returns access + refresh tokens alongside user profile data.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/auth/profile/  — fetch profile
    PATCH /api/auth/profile/  — update first/last name
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Authenticated user changes their own password.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )