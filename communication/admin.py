from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Message, MessageRecipient, Announcement, Notification, 
    EmailTemplate, SMSTemplate, CommunicationLog
)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'sender_display', 'message_type', 'status', 
        'is_urgent', 'is_important', 'sent_at', 'recipients_count'
    ]
    list_filter = [
        'message_type', 'status', 'is_urgent', 'is_important', 
        'sent_at', 'created_at'
    ]
    search_fields = ['subject', 'content', 'sender__first_name', 'sender__last_name']
    readonly_fields = ['sent_at', 'created_at', 'updated_at']
    filter_horizontal = ['recipients']
    date_hierarchy = 'sent_at'
    
    fieldsets = (
        ('Message Information', {
            'fields': ('subject', 'content', 'message_type', 'status')
        }),
        ('Recipients', {
            'fields': ('sender', 'recipients')
        }),
        ('Priority & Flags', {
            'fields': ('is_urgent', 'is_important')
        }),
        ('Attachments', {
            'fields': ('attachment',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('sent_at', 'read_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def sender_display(self, obj):
        return obj.sender.get_full_name()
    sender_display.short_description = 'Sender'
    
    def recipients_count(self, obj):
        return obj.recipients.count()
    recipients_count.short_description = 'Recipients'


@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = [
        'message_subject', 'recipient_display', 'is_read', 
        'read_at', 'is_deleted', 'created_at'
    ]
    list_filter = ['is_read', 'is_deleted', 'created_at']
    search_fields = [
        'message__subject', 'recipient__first_name', 
        'recipient__last_name'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def message_subject(self, obj):
        return obj.message.subject
    message_subject.short_description = 'Message'
    
    def recipient_display(self, obj):
        return obj.recipient.get_full_name()
    recipient_display.short_description = 'Recipient'


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'announcement_type', 'target_audience', 
        'is_published', 'is_urgent', 'is_featured', 
        'published_at', 'expires_at_display'
    ]
    list_filter = [
        'announcement_type', 'target_audience', 'is_published', 
        'is_urgent', 'is_featured', 'created_at'
    ]
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['target_classes']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Announcement Information', {
            'fields': ('title', 'content', 'announcement_type', 'target_audience')
        }),
        ('Target Classes', {
            'fields': ('target_classes',),
            'classes': ('collapse',)
        }),
        ('Publishing', {
            'fields': ('is_published', 'published_by', 'published_at')
        }),
        ('Expiry & Priority', {
            'fields': ('expires_at', 'is_urgent', 'is_featured')
        }),
        ('Attachments', {
            'fields': ('attachment',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def expires_at_display(self, obj):
        if obj.expires_at:
            if obj.is_expired:
                return format_html('<span style="color: red;">{}</span>', obj.expires_at.strftime('%Y-%m-%d %H:%M'))
            else:
                return obj.expires_at.strftime('%Y-%m-%d %H:%M')
        return '-'
    expires_at_display.short_description = 'Expires At'
    
    actions = ['publish_announcements', 'unpublish_announcements']
    
    def publish_announcements(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            is_published=True, 
            published_at=timezone.now(),
            published_by=request.user
        )
        self.message_user(request, f'{updated} announcements published successfully.')
    publish_announcements.short_description = 'Publish selected announcements'
    
    def unpublish_announcements(self, request, queryset):
        updated = queryset.update(is_published=False, published_at=None)
        self.message_user(request, f'{updated} announcements unpublished successfully.')
    unpublish_announcements.short_description = 'Unpublish selected announcements'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'recipient_display', 'notification_type', 
        'status', 'is_urgent', 'sent_at', 'read_at'
    ]
    list_filter = [
        'notification_type', 'status', 'is_urgent', 
        'email_sent', 'sms_sent', 'push_sent', 'created_at'
    ]
    search_fields = [
        'title', 'message', 'recipient__first_name', 
        'recipient__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('title', 'message', 'notification_type', 'status')
        }),
        ('Recipient', {
            'fields': ('recipient',)
        }),
        ('Related Objects', {
            'fields': ('related_message', 'related_announcement'),
            'classes': ('collapse',)
        }),
        ('Delivery Status', {
            'fields': ('sent_at', 'read_at', 'email_sent', 'sms_sent', 'push_sent')
        }),
        ('Priority', {
            'fields': ('is_urgent',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def recipient_display(self, obj):
        return obj.recipient.get_full_name()
    recipient_display.short_description = 'Recipient'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'template_type', 'subject', 'is_active', 
        'created_at', 'updated_at'
    ]
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'subject', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'template_type', 'subject', 'content')
        }),
        ('Template Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'template_type', 'content_preview', 'is_active', 
        'created_at', 'updated_at'
    ]
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'template_type', 'content')
        }),
        ('Template Variables', {
            'fields': ('variables',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = [
        'communication_type', 'recipient_display', 'status', 
        'subject', 'sent_at', 'delivered_at'
    ]
    list_filter = [
        'communication_type', 'status', 'sent_at', 'created_at'
    ]
    search_fields = [
        'subject', 'content', 'recipient__first_name', 
        'recipient__last_name'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Communication Information', {
            'fields': ('communication_type', 'status', 'subject', 'content')
        }),
        ('Recipient', {
            'fields': ('recipient',)
        }),
        ('Delivery Details', {
            'fields': ('sent_at', 'delivered_at', 'error_message')
        }),
        ('Related Objects', {
            'fields': ('related_notification',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def recipient_display(self, obj):
        return obj.recipient.get_full_name()
    recipient_display.short_description = 'Recipient'


# Customize admin site
admin.site.site_header = 'ADOM Institute - Communication'
admin.site.site_title = 'ADOM Institute Communication'
admin.site.index_title = 'Communication Management'
