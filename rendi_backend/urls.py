from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

# ------------------------------------------------------------------
# Admin cosmetics
# ------------------------------------------------------------------
admin.site.site_header = "Rendi Admin"
admin.site.site_title = "Rendi Admin Portal"
admin.site.index_title = "Welcome to Rendi"

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth endpoints
    path("api/auth/", include("apps.users.urls")),

    # JWT token refresh (shared utility endpoint)
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Assessments
    path("api/assessments/", include("apps.assessments.urls")),
]
