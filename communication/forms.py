from django import forms
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from accounts.permissions import (
    is_admin_user,
    is_platform_admin,
    user_institution_ids,
)
from .models import (
    Message, Announcement, Notification, EmailTemplate, 
    SMSTemplate, CommunicationLog
)
from students.models import Student, Class
from teachers.models import Teacher

User = get_user_model()

STAFF_MESSAGE_USER_TYPES = ['super_admin', 'administrator', 'accountant']


def message_recipients_for(user):
    """Return the users a given user is allowed to message.

    The role branches used ``hasattr(user, 'teacher')``/``hasattr(user, 'student')``
    but the related names are ``teacher_profile``/``student_profile``, so the
    student branch never matched and every user fell back to the unrestricted
    ``User.objects.all()`` queryset. The queryset is also limited to the
    sender's own institution(s) so messages cannot cross tenant boundaries.
    """
    queryset = User.objects.filter(is_active=True)

    if is_platform_admin(user):
        return queryset

    institution_ids = user_institution_ids(user) or []
    if not institution_ids:
        return queryset.none()

    # Only members of the sender's institutions are addressable.
    queryset = queryset.filter(
        models.Q(is_superuser=True) |
        models.Q(institution_memberships__institution_id__in=institution_ids)
    ).distinct()

    user_type = getattr(user, 'user_type', None)
    if is_admin_user(user):
        return queryset

    if user_type == 'student':
        # Students may message teachers and office staff, never other students.
        return queryset.exclude(user_type='student')

    if user_type == 'teacher':
        # Teachers may message students, other teachers and office staff.
        return queryset

    if user_type == 'parent':
        return queryset.exclude(user_type='parent')

    return queryset


def classes_visible_to(user):
    """Return the classes a user may target with an announcement.

    The list is limited to the user's own institution(s) so announcements
    cannot target classes of another institution.
    """
    queryset = Class.objects.select_related('academic_year__institution')
    if is_platform_admin(user):
        return queryset
    institution_ids = user_institution_ids(user) or []
    if not institution_ids:
        return queryset.none()
    return queryset.filter(
        academic_year__institution_id__in=institution_ids
    ).distinct()


class MessageForm(forms.ModelForm):
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more recipients"
    )
    
    class Meta:
        model = Message
        fields = [
            'recipients', 'subject', 'content', 'message_type',
            'is_urgent', 'is_important', 'attachment'
        ]
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'message_type': forms.Select(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['recipients'].queryset = message_recipients_for(user)
    
    def clean(self):
        cleaned_data = super().clean()
        recipients = cleaned_data.get('recipients')
        message_type = cleaned_data.get('message_type')
        
        if not recipients:
            raise forms.ValidationError("Please select at least one recipient.")
        
        if message_type == Message.MessageType.DIRECT and recipients.count() > 1:
            raise forms.ValidationError("Direct messages can only have one recipient.")
        
        return cleaned_data


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            'title', 'content', 'announcement_type', 'target_audience',
            'target_classes', 'is_published', 'expires_at', 'is_urgent',
            'is_featured', 'attachment'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'announcement_type': forms.Select(attrs={'class': 'form-control'}),
            'target_audience': forms.Select(attrs={'class': 'form-control'}),
            'target_classes': forms.CheckboxSelectMultiple(),
            'expires_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        classes = kwargs.pop('classes', None)
        super().__init__(*args, **kwargs)
        if classes is not None:
            self.fields['target_classes'].queryset = classes
        elif user is not None:
            self.fields['target_classes'].queryset = classes_visible_to(user)
    
    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise forms.ValidationError("Expiry date must be in the future.")
        return expires_at


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = [
            'recipient', 'notification_type', 'title', 'message',
            'related_message', 'related_announcement', 'is_urgent'
        ]
        widgets = {
            'recipient': forms.Select(attrs={'class': 'form-control'}),
            'notification_type': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'related_message': forms.Select(attrs={'class': 'form-control'}),
            'related_announcement': forms.Select(attrs={'class': 'form-control'}),
        }


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['name', 'template_type', 'subject', 'content', 'variables', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'variables': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables')
        try:
            if isinstance(variables, str):
                import json
                variables = json.loads(variables)
        except json.JSONDecodeError:
            raise forms.ValidationError("Variables must be valid JSON format.")
        return variables


class SMSTemplateForm(forms.ModelForm):
    class Meta:
        model = SMSTemplate
        fields = ['name', 'template_type', 'content', 'variables', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'variables': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content) > 160:
            raise forms.ValidationError("SMS content cannot exceed 160 characters.")
        return content
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables')
        try:
            if isinstance(variables, str):
                import json
                variables = json.loads(variables)
        except json.JSONDecodeError:
            raise forms.ValidationError("Variables must be valid JSON format.")
        return variables


class CommunicationLogForm(forms.ModelForm):
    class Meta:
        model = CommunicationLog
        fields = [
            'recipient', 'communication_type', 'status', 'subject',
            'content', 'sent_at', 'delivered_at', 'error_message',
            'related_notification'
        ]
        widgets = {
            'recipient': forms.Select(attrs={'class': 'form-control'}),
            'communication_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'sent_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'delivered_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'error_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'related_notification': forms.Select(attrs={'class': 'form-control'}),
        }


# Search and Filter Forms
class MessageSearchForm(forms.Form):
    subject = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search subject...'})
    )
    sender = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    message_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Message.MessageType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Message.MessageStatus.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_urgent = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_important = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['sender'].queryset = message_recipients_for(user)


class AnnouncementSearchForm(forms.Form):
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search title...'})
    )
    announcement_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Announcement.AnnouncementType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_audience = forms.ChoiceField(
        choices=[('', 'All Audiences')] + Announcement.TargetAudience.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_published = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_urgent = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_featured = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class NotificationSearchForm(forms.Form):
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search title...'})
    )
    recipient = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notification_type = forms.ChoiceField(
        choices=[('', 'All Types')] + Notification.NotificationType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Notification.NotificationStatus.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_urgent = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['recipient'].queryset = message_recipients_for(user)


# Bulk Operation Forms
class BulkMessageForm(forms.Form):
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select multiple recipients"
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
    )
    message_type = forms.ChoiceField(
        choices=Message.MessageType.choices,
        initial=Message.MessageType.BROADCAST,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_urgent = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_important = forms.BooleanField(required=False, widget=forms.CheckboxInput())


class BulkAnnouncementForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6})
    )
    announcement_type = forms.ChoiceField(
        choices=Announcement.AnnouncementType.choices,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_audience = forms.ChoiceField(
        choices=Announcement.TargetAudience.choices,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    target_classes = forms.ModelMultipleChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={'class': 'form-control', 'type': 'datetime-local'}
        )
    )
    is_urgent = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    is_featured = forms.BooleanField(required=False, widget=forms.CheckboxInput())
