"""Context processors that expose in-app notifications to every template."""


def nav_notifications(request):
    """Provide the signed-in user's unread notifications for the top bar."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    from .models import Notification

    unread = (
        Notification.objects.filter(recipient=user)
        .exclude(status=Notification.NotificationStatus.READ)
        .order_by('-created_at')
    )
    return {
        'nav_notifications': list(unread[:8]),
        'nav_notification_count': unread.count(),
    }
