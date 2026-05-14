from django.contrib import admin
from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display  = ("user", "email_type", "subject", "success", "sent_at")
    list_filter   = ("email_type", "success")
    search_fields = ("user__email", "subject")
    ordering      = ("-sent_at",)
    readonly_fields = (
        "user", "email_type", "subject", "success", "error",
        "assessment", "sent_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
