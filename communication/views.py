from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from accounts.permissions import (
    AdminRequiredMixin, AcademicStaffRequiredMixin, is_admin_user,
    is_academic_staff_user,
)

from .models import (
    Message, MessageRecipient, Announcement, Notification,
    EmailTemplate, SMSTemplate, CommunicationLog
)
from .forms import (
    MessageForm, AnnouncementForm, NotificationForm, EmailTemplateForm,
    SMSTemplateForm, CommunicationLogForm, MessageSearchForm,
    AnnouncementSearchForm, NotificationSearchForm, BulkMessageForm,
    BulkAnnouncementForm
)
from .serializers import (
    MessageSerializer, MessageCreateSerializer, MessageRecipientSerializer,
    AnnouncementSerializer, AnnouncementCreateSerializer, NotificationSerializer,
    NotificationCreateSerializer, EmailTemplateSerializer, SMSTemplateSerializer,
    CommunicationLogSerializer, MessageSummarySerializer, AnnouncementSummarySerializer,
    NotificationSummarySerializer, CommunicationReportSerializer,
    BulkMessageSerializer, BulkAnnouncementSerializer
)
from accounts.models import User
from students.models import Student, Class
from teachers.models import Teacher


# API Viewsets
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.select_related('sender').prefetch_related('recipients')
        
        # Filter based on user role and permissions
        if is_admin_user(user):
            return queryset
        else:
            # Users can see messages they sent or received
            return queryset.filter(
                Q(sender=user) | Q(recipients=user)
            ).distinct()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MessageCreateSerializer
        return MessageSerializer
    
    @action(detail=False, methods=['get'])
    def inbox(self, request):
        """Get user's inbox messages"""
        user = request.user
        messages = Message.objects.filter(recipients=user).order_by('-sent_at')
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sent(self, request):
        """Get user's sent messages"""
        user = request.user
        messages = Message.objects.filter(sender=user).order_by('-sent_at')
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark message as read"""
        message = self.get_object()
        user = request.user
        
        if user in message.recipients.all():
            MessageRecipient.objects.filter(
                message=message, recipient=user
            ).update(is_read=True, read_at=timezone.now())
            return Response({'status': 'marked as read'})
        return Response({'error': 'Not a recipient'}, status=400)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get message summary statistics"""
        user = request.user
        queryset = self.get_queryset()
        
        summary = {
            'total_messages': queryset.count(),
            'sent_messages': queryset.filter(sender=user).count(),
            'received_messages': queryset.filter(recipients=user).count(),
            'unread_messages': MessageRecipient.objects.filter(
                recipient=user, is_read=False
            ).count(),
            'urgent_messages': queryset.filter(is_urgent=True).count(),
            'messages_by_type': dict(queryset.values_list('message_type').annotate(count=Count('id'))),
        }
        
        serializer = MessageSummarySerializer(summary)
        return Response(serializer.data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Announcement.objects.select_related('published_by').prefetch_related('target_classes')
        
        # Filter based on user role and target audience
        if is_admin_user(user):
            return queryset
        
        # Filter by target audience
        if hasattr(user, 'student'):
            return queryset.filter(
                Q(target_audience__in=['all', 'students']) |
                Q(target_classes=user.student.current_class)
            ).filter(is_published=True, is_expired=False)
        elif hasattr(user, 'teacher'):
            return queryset.filter(
                target_audience__in=['all', 'teachers']
            ).filter(is_published=True, is_expired=False)
        
        return queryset.filter(is_published=True, is_expired=False)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AnnouncementCreateSerializer
        return AnnouncementSerializer
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active (published and not expired) announcements"""
        announcements = self.get_queryset().filter(
            is_published=True, is_expired=False
        ).order_by('-created_at')
        serializer = self.get_serializer(announcements, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def urgent(self, request):
        """Get urgent announcements"""
        announcements = self.get_queryset().filter(
            is_urgent=True, is_published=True, is_expired=False
        ).order_by('-created_at')
        serializer = self.get_serializer(announcements, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get announcement summary statistics"""
        queryset = self.get_queryset()
        
        summary = {
            'total_announcements': queryset.count(),
            'published_announcements': queryset.filter(is_published=True).count(),
            'urgent_announcements': queryset.filter(is_urgent=True).count(),
            'featured_announcements': queryset.filter(is_featured=True).count(),
            'expired_announcements': queryset.filter(is_expired=True).count(),
            'announcements_by_type': dict(queryset.values_list('announcement_type').annotate(count=Count('id'))),
            'announcements_by_audience': dict(queryset.values_list('target_audience').annotate(count=Count('id'))),
        }
        
        serializer = AnnouncementSummarySerializer(summary)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Notification.objects.filter(recipient=user).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return NotificationSerializer
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications"""
        notifications = self.get_queryset().filter(
            status__in=['pending', 'sent', 'delivered']
        )
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'marked as read'})
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get notification summary statistics"""
        user = request.user
        queryset = self.get_queryset()
        
        summary = {
            'total_notifications': queryset.count(),
            'unread_notifications': queryset.filter(status__in=['pending', 'sent', 'delivered']).count(),
            'urgent_notifications': queryset.filter(is_urgent=True).count(),
            'notifications_by_type': dict(queryset.values_list('notification_type').annotate(count=Count('id'))),
            'notifications_by_status': dict(queryset.values_list('status').annotate(count=Count('id'))),
        }
        
        serializer = NotificationSummarySerializer(summary)
        return Response(serializer.data)


class EmailTemplateViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return EmailTemplate.objects.filter(is_active=True)


class SMSTemplateViewSet(viewsets.ModelViewSet):
    queryset = SMSTemplate.objects.all()
    serializer_class = SMSTemplateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SMSTemplate.objects.filter(is_active=True)


class CommunicationLogViewSet(viewsets.ModelViewSet):
    queryset = CommunicationLog.objects.all()
    serializer_class = CommunicationLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return CommunicationLog.objects.all()
        return CommunicationLog.objects.filter(recipient=user)


# Web-based Views
@login_required
def communication_dashboard(request):
    """Communication dashboard view"""
    user = request.user
    
    # Get user-specific data
    if is_admin_user(user):
        # Staff dashboard
        total_messages = Message.objects.count()
        total_announcements = Announcement.objects.count()
        total_notifications = Notification.objects.count()
        recent_messages = Message.objects.select_related('sender').order_by('-sent_at')[:5]
        recent_announcements = Announcement.objects.select_related('published_by').order_by('-created_at')[:5]
    else:
        # User dashboard
        total_messages = Message.objects.filter(
            Q(sender=user) | Q(recipients=user)
        ).count()
        total_announcements = Announcement.objects.filter(
            is_published=True, is_expired=False
        ).count()
        total_notifications = Notification.objects.filter(recipient=user).count()
        recent_messages = Message.objects.filter(
            Q(sender=user) | Q(recipients=user)
        ).select_related('sender').order_by('-sent_at')[:5]
        recent_announcements = Announcement.objects.filter(
            is_published=True, is_expired=False
        ).select_related('published_by').order_by('-created_at')[:5]
    
    # Unread counts
    unread_messages = MessageRecipient.objects.filter(
        recipient=user, is_read=False
    ).count()
    unread_notifications = Notification.objects.filter(
        recipient=user, status__in=['pending', 'sent', 'delivered']
    ).count()
    
    context = {
        'total_messages': total_messages,
        'total_announcements': total_announcements,
        'total_notifications': total_notifications,
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications,
        'recent_messages': recent_messages,
        'recent_announcements': recent_announcements,
    }
    
    return render(request, 'communication/dashboard.html', context)


class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'communication/message_list.html'
    context_object_name = 'messages'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.select_related('sender').prefetch_related('recipients')
        
        # Apply filters
        form = MessageSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('subject'):
                queryset = queryset.filter(subject__icontains=form.cleaned_data['subject'])
            if form.cleaned_data.get('sender'):
                queryset = queryset.filter(sender=form.cleaned_data['sender'])
            if form.cleaned_data.get('message_type'):
                queryset = queryset.filter(message_type=form.cleaned_data['message_type'])
            if form.cleaned_data.get('status'):
                queryset = queryset.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('is_urgent'):
                queryset = queryset.filter(is_urgent=True)
            if form.cleaned_data.get('is_important'):
                queryset = queryset.filter(is_important=True)
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(sent_at__date__gte=form.cleaned_data['date_from'])
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(sent_at__date__lte=form.cleaned_data['date_to'])
        
        # Filter based on user role
        if is_admin_user(user):
            return queryset.order_by('-sent_at')
        else:
            return queryset.filter(
                Q(sender=user) | Q(recipients=user)
            ).distinct().order_by('-sent_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = MessageSearchForm(self.request.GET)
        return context


class InboxView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'communication/inbox.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        return Message.objects.filter(
            recipients=self.request.user,
            message_recipients__recipient=self.request.user,
            message_recipients__is_deleted=False,
        ).select_related('sender').prefetch_related('recipients').distinct().order_by('-sent_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_receipts = MessageRecipient.objects.filter(
            recipient=self.request.user,
            is_deleted=False,
        )
        context['unread_message_ids'] = set(
            user_receipts.filter(is_read=False).values_list('message_id', flat=True)
        )
        context['unread_count'] = len(context['unread_message_ids'])
        context['important_count'] = self.get_queryset().filter(
            Q(is_urgent=True) | Q(is_important=True)
        ).count()
        context['total_received_count'] = self.get_queryset().count()
        return context


class MessageCreateView(LoginRequiredMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'communication/message_form.html'
    success_url = reverse_lazy('communication:message_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.sender = self.request.user
        messages.success(self.request, 'Message sent successfully.')
        return super().form_valid(form)


class MessageDetailView(LoginRequiredMixin, DetailView):
    model = Message
    template_name = 'communication/message_detail.html'
    context_object_name = 'message'
    
    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.select_related('sender').prefetch_related('recipients')
        if is_admin_user(user):
            return queryset
        return queryset.filter(Q(sender=user) | Q(recipients=user)).distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mark as read if user is recipient
        if self.request.user in self.object.recipients.all():
            MessageRecipient.objects.filter(
                message=self.object, recipient=self.request.user
            ).update(is_read=True, read_at=timezone.now())
        return context


class AnnouncementListView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'communication/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        queryset = Announcement.objects.select_related('published_by').prefetch_related('target_classes')
        
        # Apply filters
        form = AnnouncementSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('title'):
                queryset = queryset.filter(title__icontains=form.cleaned_data['title'])
            if form.cleaned_data.get('announcement_type'):
                queryset = queryset.filter(announcement_type=form.cleaned_data['announcement_type'])
            if form.cleaned_data.get('target_audience'):
                queryset = queryset.filter(target_audience=form.cleaned_data['target_audience'])
            if form.cleaned_data.get('is_published') is not None:
                queryset = queryset.filter(is_published=form.cleaned_data['is_published'])
            if form.cleaned_data.get('is_urgent'):
                queryset = queryset.filter(is_urgent=True)
            if form.cleaned_data.get('is_featured'):
                queryset = queryset.filter(is_featured=True)
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=form.cleaned_data['date_from'])
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=form.cleaned_data['date_to'])
        
        # Filter based on user role
        if is_admin_user(user):
            return queryset.order_by('-created_at')
        else:
            return queryset.filter(
                is_published=True, is_expired=False
            ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AnnouncementSearchForm(self.request.GET)
        return context


class AnnouncementCreateView(LoginRequiredMixin, AcademicStaffRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'communication/announcement_form.html'
    success_url = reverse_lazy('communication:announcement_list')
    
    def form_valid(self, form):
        form.instance.published_by = self.request.user
        messages.success(self.request, 'Announcement created successfully.')
        return super().form_valid(form)


class AnnouncementDetailView(LoginRequiredMixin, DetailView):
    model = Announcement
    template_name = 'communication/announcement_detail.html'
    context_object_name = 'announcement'
    
    def get_queryset(self):
        user = self.request.user
        if is_admin_user(user):
            return Announcement.objects.select_related('published_by').prefetch_related('target_classes')
        return Announcement.objects.filter(
            is_published=True, is_expired=False
        ).select_related('published_by').prefetch_related('target_classes')


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'communication/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(recipient=user)
        
        # Apply filters
        form = NotificationSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('title'):
                queryset = queryset.filter(title__icontains=form.cleaned_data['title'])
            if form.cleaned_data.get('notification_type'):
                queryset = queryset.filter(notification_type=form.cleaned_data['notification_type'])
            if form.cleaned_data.get('status'):
                queryset = queryset.filter(status=form.cleaned_data['status'])
            if form.cleaned_data.get('is_urgent'):
                queryset = queryset.filter(is_urgent=True)
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=form.cleaned_data['date_from'])
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=form.cleaned_data['date_to'])
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = NotificationSearchForm(self.request.GET)
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = 'communication/notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        if is_admin_user(self.request.user):
            return Notification.objects.select_related('recipient', 'related_message', 'related_announcement')
        return Notification.objects.filter(recipient=self.request.user).select_related(
            'recipient', 'related_message', 'related_announcement'
        )


class NotificationUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Notification
    form_class = NotificationForm
    template_name = 'communication/notification_form.html'
    success_url = reverse_lazy('communication:notification_list')

    def get_queryset(self):
        if is_admin_user(self.request.user):
            return Notification.objects.all()
        return Notification.objects.filter(recipient=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Notification updated successfully.')
        return super().form_valid(form)


class EmailTemplateListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = EmailTemplate
    template_name = 'communication/email_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def get_queryset(self):
        return EmailTemplate.objects.order_by('name')


class EmailTemplateDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = EmailTemplate
    template_name = 'communication/email_template_detail_modern.html'
    context_object_name = 'template'


class EmailTemplateCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'communication/email_template_form_modern.html'
    success_url = reverse_lazy('communication:email_template_list')

    def form_valid(self, form):
        messages.success(self.request, 'Email template created successfully.')
        return super().form_valid(form)


class EmailTemplateUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'communication/email_template_form_modern.html'
    success_url = reverse_lazy('communication:email_template_list')

    def form_valid(self, form):
        messages.success(self.request, 'Email template updated successfully.')
        return super().form_valid(form)


class SMSTemplateListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = SMSTemplate
    template_name = 'communication/sms_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def get_queryset(self):
        return SMSTemplate.objects.order_by('name')


class SMSTemplateDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = SMSTemplate
    template_name = 'communication/sms_template_detail_modern.html'
    context_object_name = 'template'


class SMSTemplateCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = SMSTemplate
    form_class = SMSTemplateForm
    template_name = 'communication/sms_template_form_modern.html'
    success_url = reverse_lazy('communication:sms_template_list')

    def form_valid(self, form):
        messages.success(self.request, 'SMS template created successfully.')
        return super().form_valid(form)


class SMSTemplateUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = SMSTemplate
    form_class = SMSTemplateForm
    template_name = 'communication/sms_template_form_modern.html'
    success_url = reverse_lazy('communication:sms_template_list')

    def form_valid(self, form):
        messages.success(self.request, 'SMS template updated successfully.')
        return super().form_valid(form)


class CommunicationLogListView(LoginRequiredMixin, ListView):
    model = CommunicationLog
    template_name = 'communication/communication_log_list.html'
    context_object_name = 'logs'
    paginate_by = 20

    def get_queryset(self):
        queryset = CommunicationLog.objects.select_related('recipient', 'related_notification')
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(recipient=self.request.user)


class CommunicationLogDetailView(LoginRequiredMixin, DetailView):
    model = CommunicationLog
    template_name = 'communication/communication_log_detail.html'
    context_object_name = 'log'

    def get_queryset(self):
        queryset = CommunicationLog.objects.select_related('recipient', 'related_notification')
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(recipient=self.request.user)


# Bulk Operations
@login_required
@user_passes_test(is_academic_staff_user)
def bulk_message(request):
    """Bulk message sending"""
    if request.method == 'POST':
        form = BulkMessageForm(request.POST)
        if form.is_valid():
            recipient_ids = form.cleaned_data['recipient_ids']
            subject = form.cleaned_data['subject']
            content = form.cleaned_data['content']
            message_type = form.cleaned_data['message_type']
            is_urgent = form.cleaned_data['is_urgent']
            is_important = form.cleaned_data['is_important']
            
            # Create message
            message = Message.objects.create(
                sender=request.user,
                subject=subject,
                content=content,
                message_type=message_type,
                is_urgent=is_urgent,
                is_important=is_important
            )
            message.recipients.set(recipient_ids)
            
            messages.success(request, f'Message sent to {len(recipient_ids)} recipients successfully.')
            return redirect('communication:message_list')
    else:
        form = BulkMessageForm()
    
    return render(request, 'communication/bulk_message.html', {'form': form})


@login_required
@user_passes_test(is_academic_staff_user)
def bulk_announcement(request):
    """Bulk announcement creation"""
    if request.method == 'POST':
        form = BulkAnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.published_by = request.user
            announcement.save()
            form.save_m2m()
            
            messages.success(request, 'Announcement created successfully.')
            return redirect('communication:announcement_list')
    else:
        form = BulkAnnouncementForm()
    
    return render(request, 'communication/bulk_announcement.html', {'form': form})


# AJAX Views
@login_required
def get_users_for_message(request):
    """Get users for message composition"""
    user_type = request.GET.get('user_type', '')
    class_id = request.GET.get('class_id', '')
    
    users = User.objects.all()
    
    if user_type == 'students':
        users = User.objects.filter(student__isnull=False)
        if class_id:
            users = users.filter(student__current_class_id=class_id)
    elif user_type == 'teachers':
        users = User.objects.filter(teacher__isnull=False)
    elif user_type == 'staff':
        users = User.objects.filter(user_type__in=['super_admin', 'administrator', 'accountant'])
    
    data = [{'id': user.id, 'name': user.get_full_name(), 'email': user.email} for user in users]
    return JsonResponse({'users': data})


@login_required
def mark_notification_read(request, notification_id):
    """Mark notification as read via AJAX"""
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)


@login_required
def get_notification_count(request):
    """Get unread notification count"""
    count = Notification.objects.filter(
        recipient=request.user,
        status__in=['pending', 'sent', 'delivered']
    ).count()
    return JsonResponse({'count': count})


@login_required
def get_message_count(request):
    """Get unread message count"""
    count = MessageRecipient.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    return JsonResponse({'count': count})

# Report Views
@login_required
@user_passes_test(is_admin_user)
def communication_report(request):
    """Generate communication reports"""
    if not is_admin_user(request.user):
        messages.error(request, 'Access denied. Administrators only.')
        return redirect('communication:dashboard')
    
    # Get report data
    period = request.GET.get('period', 'month')
    
    # Calculate statistics based on period
    if period == 'week':
        start_date = timezone.now() - timezone.timedelta(days=7)
    elif period == 'month':
        start_date = timezone.now() - timezone.timedelta(days=30)
    else:  # year
        start_date = timezone.now() - timezone.timedelta(days=365)
    
    # Message statistics
    messages = Message.objects.filter(sent_at__gte=start_date)
    message_stats = {
        'total': messages.count(),
        'by_type': dict(messages.values_list('message_type').annotate(count=Count('id'))),
        'urgent': messages.filter(is_urgent=True).count(),
    }
    
    # Announcement statistics
    announcements = Announcement.objects.filter(created_at__gte=start_date)
    announcement_stats = {
        'total': announcements.count(),
        'published': announcements.filter(is_published=True).count(),
        'urgent': announcements.filter(is_urgent=True).count(),
    }
    
    # Notification statistics
    notifications = Notification.objects.filter(created_at__gte=start_date)
    notification_stats = {
        'total': notifications.count(),
        'sent': notifications.filter(status='sent').count(),
        'read': notifications.filter(status='read').count(),
    }
    
    context = {
        'period': period,
        'message_stats': message_stats,
        'announcement_stats': announcement_stats,
        'notification_stats': notification_stats,
    }
    
    return render(request, 'communication/communication_report_modern.html', context)

