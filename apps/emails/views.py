from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(["POST"])
@permission_classes([AllowAny])
def run_scheduled_emails(request):
    secret = request.headers.get("X-Cron-Secret")
    if secret != settings.CRON_SECRET:
        return Response({"error": "Forbidden"}, status=403)

    from apps.emails.tasks import (
        send_inactivity_reminders_task,
        send_advisor_followup_task,
    )
    reminders = send_inactivity_reminders_task()
    followups = send_advisor_followup_task()

    return Response({"reminders_sent": reminders, "followups_sent": followups})
