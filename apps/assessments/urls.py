from django.urls import path
from .views import (
    SubmitAssessmentView,
    LatestAssessmentView,
    AssessmentHistoryView,
    AssessmentDetailView,
    ComparisonView,
)

urlpatterns = [
    path("submit/",   SubmitAssessmentView.as_view(),   name="assessment_submit"),
    path("latest/",   LatestAssessmentView.as_view(),   name="assessment_latest"),
    path("history/",  AssessmentHistoryView.as_view(),  name="assessment_history"),
    path("compare/",  ComparisonView.as_view(),          name="assessment_compare"),
    path("<int:pk>/", AssessmentDetailView.as_view(),   name="assessment_detail"),
]
