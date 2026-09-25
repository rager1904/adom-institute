from django import forms

from accounts.models import Institution
from accounts.permissions import is_platform_admin, user_institution_ids
from .models import AIConsent, AIConversation, AIMessage, AgentTask, KnowledgeDocument


class KnowledgeDocumentForm(forms.ModelForm):
    class Meta:
        model = KnowledgeDocument
        fields = ['institution', 'title', 'source_type', 'subject', 'grade_level', 'access_scope', 'file']
        widgets = {
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'grade_level': forms.TextInput(attrs={'class': 'form-control'}),
            'access_scope': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields['institution'].queryset = Institution.objects.none()
            return
        if is_platform_admin(user):
            self.fields['institution'].queryset = Institution.objects.filter(is_active=True)
        else:
            institution_ids = user_institution_ids(user)
            self.fields['institution'].queryset = Institution.objects.filter(id__in=institution_ids or [], is_active=True)


class AgentTaskForm(forms.ModelForm):
    class Meta:
        model = AgentTask
        fields = ['institution', 'agent_key', 'model_profile', 'requires_human_approval', 'input_payload']
        widgets = {
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'agent_key': forms.Select(attrs={'class': 'form-select'}),
            'model_profile': forms.TextInput(attrs={'class': 'form-control'}),
            'requires_human_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'input_payload': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields['institution'].queryset = Institution.objects.none()
        elif is_platform_admin(user):
            self.fields['institution'].queryset = Institution.objects.filter(is_active=True)
        else:
            institution_ids = user_institution_ids(user)
            self.fields['institution'].queryset = Institution.objects.filter(id__in=institution_ids or [], is_active=True)


class AIConsentForm(forms.ModelForm):
    class Meta:
        model = AIConsent
        fields = ['institution', 'status', 'allow_personalization', 'allow_academic_analysis', 'allow_opportunity_matching']
        widgets = {
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'allow_personalization': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_academic_analysis': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_opportunity_matching': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields['institution'].queryset = Institution.objects.none()
        elif is_platform_admin(user):
            self.fields['institution'].queryset = Institution.objects.filter(is_active=True)
        else:
            institution_ids = user_institution_ids(user)
            self.fields['institution'].queryset = Institution.objects.filter(id__in=institution_ids or [], is_active=True)


class AIConversationForm(forms.ModelForm):
    class Meta:
        model = AIConversation
        fields = ['institution', 'agent_key', 'title']
        widgets = {
            'institution': forms.Select(attrs={'class': 'form-select'}),
            'agent_key': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields['institution'].queryset = Institution.objects.none()
        elif is_platform_admin(user):
            self.fields['institution'].queryset = Institution.objects.filter(is_active=True)
        else:
            institution_ids = user_institution_ids(user)
            self.fields['institution'].queryset = Institution.objects.filter(id__in=institution_ids or [], is_active=True)


class AIMessageForm(forms.ModelForm):
    class Meta:
        model = AIMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ask ADOM Institute...'}),
        }
