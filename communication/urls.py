from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'communication'

# API Router
router = DefaultRouter()
router.register(r'messages', views.MessageViewSet, basename='message')
router.register(r'announcements', views.AnnouncementViewSet, basename='announcement')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'email-templates', views.EmailTemplateViewSet, basename='email-template')
router.register(r'sms-templates', views.SMSTemplateViewSet, basename='sms-template')
router.register(r'communication-logs', views.CommunicationLogViewSet, basename='communication-log')

# Web-based URL patterns
urlpatterns = [
    # Dashboard
    path('', views.communication_dashboard, name='dashboard'),
    
    # Messages
    path('inbox/', views.InboxView.as_view(), name='inbox'),
    path('messages/', views.MessageListView.as_view(), name='message_list'),
    path('messages/create/', views.MessageCreateView.as_view(), name='message_create'),
    path('messages/<int:pk>/', views.MessageDetailView.as_view(), name='message_detail'),
    
    # Announcements
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/create/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<int:pk>/', views.AnnouncementDetailView.as_view(), name='announcement_detail'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('notifications/<int:pk>/update/', views.NotificationUpdateView.as_view(), name='notification_update'),

    # Templates and logs
    path('email-templates/', views.EmailTemplateListView.as_view(), name='email_template_list'),
    path('email-templates/create/', views.EmailTemplateCreateView.as_view(), name='email_template_create'),
    path('email-templates/<int:pk>/', views.EmailTemplateDetailView.as_view(), name='email_template_detail'),
    path('email-templates/<int:pk>/update/', views.EmailTemplateUpdateView.as_view(), name='email_template_update'),
    path('sms-templates/', views.SMSTemplateListView.as_view(), name='sms_template_list'),
    path('sms-templates/create/', views.SMSTemplateCreateView.as_view(), name='sms_template_create'),
    path('sms-templates/<int:pk>/', views.SMSTemplateDetailView.as_view(), name='sms_template_detail'),
    path('sms-templates/<int:pk>/update/', views.SMSTemplateUpdateView.as_view(), name='sms_template_update'),
    path('logs/', views.CommunicationLogListView.as_view(), name='communication_log_list'),
    path('logs/<int:pk>/', views.CommunicationLogDetailView.as_view(), name='communication_log_detail'),
    path('reports/', views.communication_report, name='communication_report'),
    
    # AJAX endpoints
    path('ajax/notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('ajax/notifications/count/', views.get_notification_count, name='get_notification_count'),
    path('ajax/messages/count/', views.get_message_count, name='get_message_count'),
    
    # API URLs
    path('api/', include(router.urls)),
]
