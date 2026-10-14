"""Helpers for creating in-app notifications for users and administrators."""
from django.db.models import Q
from django.utils import timezone

from .models import Notification


def create_notification(
    recipient,
    *,
    title,
    message,
    notification_type=Notification.NotificationType.SYSTEM,
    url='',
    action_label='',
    is_urgent=False,
):
    """Create a single in-app notification that shows as unread."""
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url or '',
        action_label=action_label or '',
        is_urgent=is_urgent,
        status=Notification.NotificationStatus.SENT,
        sent_at=timezone.now(),
    )


def notify_platform_admins(
    *,
    title,
    message,
    url='',
    action_label='',
    notification_type=Notification.NotificationType.APPROVAL,
    is_urgent=False,
):
    """Notify every active platform administrator (super admins)."""
    from accounts.models import User

    admins = (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(user_type='super_admin'))
        .distinct()
    )
    return [
        create_notification(
            admin,
            title=title,
            message=message,
            notification_type=notification_type,
            url=url,
            action_label=action_label,
            is_urgent=is_urgent,
        )
        for admin in admins
    ]


def notify_institution_admins(
    institution,
    *,
    title,
    message,
    url='',
    action_label='',
    notification_type=Notification.NotificationType.SYSTEM,
    is_urgent=False,
):
    """Notify the owners and administrators of a single institution."""
    from accounts.models import InstitutionMembership, User

    admin_roles = {
        InstitutionMembership.MembershipRole.OWNER,
        InstitutionMembership.MembershipRole.ADMINISTRATOR,
    }
    recipients = (
        User.objects.filter(
            is_active=True,
            institution_memberships__institution=institution,
            institution_memberships__role__in=admin_roles,
            institution_memberships__is_active=True,
        )
        .distinct()
    )
    return [
        create_notification(
            user,
            title=title,
            message=message,
            notification_type=notification_type,
            url=url,
            action_label=action_label,
            is_urgent=is_urgent,
        )
        for user in recipients
    ]
