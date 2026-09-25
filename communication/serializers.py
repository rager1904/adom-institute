from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Message, MessageRecipient, Announcement, Notification,
    EmailTemplate, SMSTemplate, CommunicationLog
)
from students.models import Student, Class
from teachers.models import Teacher

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'user_type']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_user_type(self, obj):
        if getattr(obj, 'user_type', None):
            return obj.user_type
        if hasattr(obj, 'teacher'):
            return 'teacher'
        if hasattr(obj, 'student'):
            return 'student'
        return 'user'


class MessageRecipientSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='recipient',
        write_only=True
    )
    
    class Meta:
        model = MessageRecipient
        fields = ['id', 'recipient', 'recipient_id', 'is_read', 'read_at', 'is_deleted', 'created_at']
        read_only_fields = ['created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    recipients = UserSerializer(many=True, read_only=True)
    recipients_count = serializers.SerializerMethodField()
    message_recipients = MessageRecipientSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipients', 'recipients_count', 'message_recipients',
            'subject', 'content', 'message_type', 'status', 'sent_at', 'read_at',
            'attachment', 'is_urgent', 'is_important', 'created_at', 'updated_at'
        ]
        read_only_fields = ['sender', 'sent_at', 'created_at', 'updated_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        help_text="List of recipient user IDs"
    )
    
    class Meta:
        model = Message
        fields = [
            'recipient_ids', 'subject', 'content', 'message_type',
            'is_urgent', 'is_important', 'attachment'
        ]
    
    def create(self, validated_data):
        recipient_ids = validated_data.pop('recipient_ids')
        message = Message.objects.create(
            sender=self.context['request'].user,
            **validated_data
        )
        message.recipients.set(recipient_ids)
        return message
    
    def validate_recipient_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one recipient is required.")
        
        message_type = self.initial_data.get('message_type', Message.MessageType.DIRECT)
        if message_type == Message.MessageType.DIRECT and len(value) > 1:
            raise serializers.ValidationError("Direct messages can only have one recipient.")
        
        # Validate that all recipient IDs exist
        existing_users = User.objects.filter(id__in=value)
        if len(existing_users) != len(value):
            raise serializers.ValidationError("One or more recipient IDs are invalid.")
        
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    published_by = UserSerializer(read_only=True)
    target_classes = serializers.SerializerMethodField()
    
    class Meta:
        model = Announcement
        fields = [
            'id', 'title', 'content', 'announcement_type', 'target_audience',
            'target_classes', 'is_published', 'published_at', 'published_by',
            'expires_at', 'is_urgent', 'is_featured', 'attachment',
            'is_expired', 'created_at', 'updated_at'
        ]
        read_only_fields = ['published_by', 'created_at', 'updated_at']


class AnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            'title', 'content', 'announcement_type', 'target_audience',
            'target_classes', 'is_published', 'expires_at', 'is_urgent',
            'is_featured', 'attachment'
        ]
    
    def create(self, validated_data):
        announcement = Announcement.objects.create(
            published_by=self.context['request'].user,
            **validated_data
        )
        return announcement
    
    def validate_expires_at(self, value):
        from django.utils import timezone
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    related_message = MessageSerializer(read_only=True)
    related_announcement = AnnouncementSerializer(read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'notification_type', 'title', 'message',
            'related_message', 'related_announcement', 'status', 'sent_at',
            'read_at', 'email_sent', 'sms_sent', 'push_sent', 'is_urgent',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['sent_at', 'created_at', 'updated_at']


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'recipient', 'notification_type', 'title', 'message',
            'related_message', 'related_announcement', 'is_urgent'
        ]
    
    def create(self, validated_data):
        notification = Notification.objects.create(**validated_data)
        return notification


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'template_type', 'subject', 'content',
            'variables', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SMSTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSTemplate
        fields = [
            'id', 'name', 'template_type', 'content', 'variables',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_content(self, value):
        if len(value) > 160:
            raise serializers.ValidationError("SMS content cannot exceed 160 characters.")
        return value


class CommunicationLogSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)
    related_notification = NotificationSerializer(read_only=True)
    
    class Meta:
        model = CommunicationLog
        fields = [
            'id', 'recipient', 'communication_type', 'status', 'subject',
            'content', 'sent_at', 'delivered_at', 'error_message',
            'related_notification', 'created_at'
        ]
        read_only_fields = ['created_at']


# Summary and Report Serializers
class MessageSummarySerializer(serializers.Serializer):
    total_messages = serializers.IntegerField()
    sent_messages = serializers.IntegerField()
    delivered_messages = serializers.IntegerField()
    read_messages = serializers.IntegerField()
    failed_messages = serializers.IntegerField()
    urgent_messages = serializers.IntegerField()
    important_messages = serializers.IntegerField()
    messages_by_type = serializers.DictField()
    messages_by_status = serializers.DictField()


class AnnouncementSummarySerializer(serializers.Serializer):
    total_announcements = serializers.IntegerField()
    published_announcements = serializers.IntegerField()
    urgent_announcements = serializers.IntegerField()
    featured_announcements = serializers.IntegerField()
    expired_announcements = serializers.IntegerField()
    announcements_by_type = serializers.DictField()
    announcements_by_audience = serializers.DictField()


class NotificationSummarySerializer(serializers.Serializer):
    total_notifications = serializers.IntegerField()
    sent_notifications = serializers.IntegerField()
    delivered_notifications = serializers.IntegerField()
    read_notifications = serializers.IntegerField()
    failed_notifications = serializers.IntegerField()
    urgent_notifications = serializers.IntegerField()
    notifications_by_type = serializers.DictField()
    notifications_by_status = serializers.DictField()


class CommunicationReportSerializer(serializers.Serializer):
    period = serializers.CharField()
    total_communications = serializers.IntegerField()
    successful_communications = serializers.IntegerField()
    failed_communications = serializers.IntegerField()
    success_rate = serializers.FloatField()
    communications_by_type = serializers.DictField()
    communications_by_status = serializers.DictField()
    top_recipients = serializers.ListField()
    communication_trends = serializers.ListField()


# Bulk Operation Serializers
class BulkMessageSerializer(serializers.Serializer):
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of recipient user IDs"
    )
    subject = serializers.CharField(max_length=200)
    content = serializers.CharField()
    message_type = serializers.ChoiceField(choices=Message.MessageType.choices)
    is_urgent = serializers.BooleanField(default=False)
    is_important = serializers.BooleanField(default=False)
    
    def validate_recipient_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one recipient is required.")
        
        # Validate that all recipient IDs exist
        existing_users = User.objects.filter(id__in=value)
        if len(existing_users) != len(value):
            raise serializers.ValidationError("One or more recipient IDs are invalid.")
        
        return value


class BulkAnnouncementSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    content = serializers.CharField()
    announcement_type = serializers.ChoiceField(choices=Announcement.AnnouncementType.choices)
    target_audience = serializers.ChoiceField(choices=Announcement.TargetAudience.choices)
    target_class_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    expires_at = serializers.DateTimeField(required=False)
    is_urgent = serializers.BooleanField(default=False)
    is_featured = serializers.BooleanField(default=False)
    
    def validate_target_class_ids(self, value):
        if value:
            # Validate that all class IDs exist
            existing_classes = Class.objects.filter(id__in=value)
            if len(existing_classes) != len(value):
                raise serializers.ValidationError("One or more class IDs are invalid.")
        return value
    
    def validate_expires_at(self, value):
        from django.utils import timezone
        if value and value <= timezone.now():
            raise serializers.ValidationError("Expiry date must be in the future.")
        return value


# Template Variable Serializers
class TemplateVariableSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    example = serializers.CharField()
    required = serializers.BooleanField(default=False)


class EmailTemplateWithVariablesSerializer(EmailTemplateSerializer):
    available_variables = TemplateVariableSerializer(many=True, read_only=True)
    
    class Meta(EmailTemplateSerializer.Meta):
        fields = EmailTemplateSerializer.Meta.fields + ['available_variables']


class SMSTemplateWithVariablesSerializer(SMSTemplateSerializer):
    available_variables = TemplateVariableSerializer(many=True, read_only=True)
    
    class Meta(SMSTemplateSerializer.Meta):
        fields = SMSTemplateSerializer.Meta.fields + ['available_variables']
