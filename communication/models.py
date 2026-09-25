from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import User
from accounts.validators import document_upload_validators
from students.models import Student, Class
from teachers.models import Teacher


class Message(models.Model):
    class MessageType(models.TextChoices):
        DIRECT = 'direct', _('Direct Message')
        GROUP = 'group', _('Group Message')
        BROADCAST = 'broadcast', _('Broadcast Message')
    
    class MessageStatus(models.TextChoices):
        SENT = 'sent', _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        READ = 'read', _('Read')
        FAILED = 'failed', _('Failed')
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipients = models.ManyToManyField(User, related_name='received_messages')
    
    subject = models.CharField(max_length=200)
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.DIRECT)
    
    # Message status
    status = models.CharField(max_length=20, choices=MessageStatus.choices, default=MessageStatus.SENT)
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # Attachments
    attachment = models.FileField(
        upload_to='message_attachments/',
        blank=True,
        null=True,
        validators=document_upload_validators,
    )
    
    # Priority
    is_urgent = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'communication_message'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['sender', 'status', 'sent_at'], name='comm_message_sender_idx'),
            models.Index(fields=['message_type', 'sent_at'], name='comm_message_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.subject} - {self.sender.get_full_name()}"


class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='message_recipients')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='message_recipients')
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'communication_message_recipient'
        unique_together = ('message', 'recipient')
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'is_deleted'], name='comm_recipient_state_idx'),
        ]
    
    def __str__(self):
        return f"{self.message.subject} - {self.recipient.get_full_name()}"


class Announcement(models.Model):
    class AnnouncementType(models.TextChoices):
        GENERAL = 'general', _('General')
        ACADEMIC = 'academic', _('Academic')
        EVENT = 'event', _('Event')
        EMERGENCY = 'emergency', _('Emergency')
        HOLIDAY = 'holiday', _('Holiday')
    
    class TargetAudience(models.TextChoices):
        ALL = 'all', _('All')
        STUDENTS = 'students', _('Students')
        TEACHERS = 'teachers', _('Teachers')
        PARENTS = 'parents', _('Parents')
        ADMINISTRATORS = 'administrators', _('Administrators')
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=AnnouncementType.choices)
    target_audience = models.CharField(max_length=20, choices=TargetAudience.choices)
    
    # Target specific classes or groups
    target_classes = models.ManyToManyField(Class, blank=True, related_name='announcements')
    
    # Publishing details
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='published_announcements')
    
    # Expiry
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Priority
    is_urgent = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Attachments
    attachment = models.FileField(
        upload_to='announcement_attachments/',
        blank=True,
        null=True,
        validators=document_upload_validators,
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'communication_announcement'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(expires_at__isnull=True) | models.Q(expires_at__gte=models.F('published_at')) | models.Q(published_at__isnull=True),
                name='comm_announce_expiry_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['target_audience', 'is_published', 'expires_at'], name='comm_announce_target_idx'),
            models.Index(fields=['announcement_type', 'is_published'], name='comm_announce_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_announcement_type_display()})"
    
    @property
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        MESSAGE = 'message', _('Message')
        ANNOUNCEMENT = 'announcement', _('Announcement')
        ATTENDANCE = 'attendance', _('Attendance')
        EXAM = 'exam', _('Exam')
        FEE = 'fee', _('Fee')
        ASSIGNMENT = 'assignment', _('Assignment')
        SYSTEM = 'system', _('System')
    
    class NotificationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENT = 'sent', _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        READ = 'read', _('Read')
        FAILED = 'failed', _('Failed')
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Related objects
    related_message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    related_announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    # Notification status
    status = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.PENDING)
    sent_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    # Delivery methods
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    
    # Priority
    is_urgent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'communication_notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status', 'created_at'], name='comm_notif_recipient_idx'),
            models.Index(fields=['notification_type', 'status'], name='comm_notif_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"


class EmailTemplate(models.Model):
    class TemplateType(models.TextChoices):
        WELCOME = 'welcome', _('Welcome Email')
        PASSWORD_RESET = 'password_reset', _('Password Reset')
        FEE_REMINDER = 'fee_reminder', _('Fee Reminder')
        EXAM_SCHEDULE = 'exam_schedule', _('Exam Schedule')
        ATTENDANCE_ALERT = 'attendance_alert', _('Attendance Alert')
        ANNOUNCEMENT = 'announcement', _('Announcement')
        CUSTOM = 'custom', _('Custom')
    
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    
    # Template variables
    variables = models.JSONField(default=dict, help_text='Available template variables')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'communication_email_template'
        indexes = [
            models.Index(fields=['template_type', 'is_active'], name='comm_email_template_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class SMSTemplate(models.Model):
    class TemplateType(models.TextChoices):
        WELCOME = 'welcome', _('Welcome SMS')
        ATTENDANCE_ALERT = 'attendance_alert', _('Attendance Alert')
        FEE_REMINDER = 'fee_reminder', _('Fee Reminder')
        EXAM_SCHEDULE = 'exam_schedule', _('Exam Schedule')
        ANNOUNCEMENT = 'announcement', _('Announcement')
        CUSTOM = 'custom', _('Custom')
    
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=20, choices=TemplateType.choices)
    content = models.TextField()
    
    # Template variables
    variables = models.JSONField(default=dict, help_text='Available template variables')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'communication_sms_template'
        indexes = [
            models.Index(fields=['template_type', 'is_active'], name='comm_sms_template_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class CommunicationLog(models.Model):
    class CommunicationType(models.TextChoices):
        EMAIL = 'email', _('Email')
        SMS = 'sms', _('SMS')
        PUSH = 'push', _('Push Notification')
        IN_APP = 'in_app', _('In-App Notification')
    
    class CommunicationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENT = 'sent', _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        FAILED = 'failed', _('Failed')
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='communication_logs')
    communication_type = models.CharField(max_length=20, choices=CommunicationType.choices)
    status = models.CharField(max_length=20, choices=CommunicationStatus.choices, default=CommunicationStatus.PENDING)
    
    subject = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    
    # Delivery details
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Related objects
    related_notification = models.ForeignKey(Notification, on_delete=models.CASCADE, null=True, blank=True, related_name='communication_logs')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'communication_communication_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status', 'created_at'], name='comm_log_recipient_idx'),
            models.Index(fields=['communication_type', 'status'], name='comm_log_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.communication_type} - {self.recipient.get_full_name()} ({self.status})"
