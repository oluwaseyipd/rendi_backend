from django.urls import path
from .views import GenerateReferralView, ReferralStatsView

urlpatterns = [
    path("generate/", GenerateReferralView.as_view(), name="referral_generate"),
    path("stats/",    ReferralStatsView.as_view(),    name="referral_stats"),
]