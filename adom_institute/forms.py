from django import forms

from accounts.models import Institution
from accounts.permissions import is_platform_admin, user_institution_ids
from .agents import (
    ADMIN_AGENT_KEYS, agent_choices_for_user, requires_human_approval,
)
from .models import AIConsent, AIConversation, AIMessage, AgentTask, KnowledgeDocument


def institution_choices_for(user):
    """Limit the institution selector to the institutions the user may use."""
    if user is None:
        return Institution.objects.none()
    if is_platform_admin(user):
        return Institution.objects.filter(is_active=True)
    institution_ids = user_institution_ids(user)
    return Institution.objects.filter(id__in=institution_ids or [], is_active=True)


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
        self.fields['institution'].queryset = institution_choices_for(user)


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
        self.fields['institution'].queryset = institution_choices_for(user)
        # Only the agents the account may use are offered, so the form cannot
        # queue institutional work the role is not cleared for.
        self.fields['agent_key'].choices = agent_choices_for_user(user)
        # Work that changes shared data is reviewed by a human, so the option
        # starts checked.
        self.initial.setdefault('requires_human_approval', True)
        self.user = user

    def clean(self):
        cleaned_data = super().clean()
        agent_key = cleaned_data.get('agent_key')
        if not agent_key:
            return cleaned_data
        if agent_key not in dict(agent_choices_for_user(self.user)):
            self.add_error('agent_key', 'You cannot use this agent for your role.')
            return cleaned_data
        if (
            agent_key in ADMIN_AGENT_KEYS
            and not cleaned_data.get('requires_human_approval')
        ):
            self.add_error(
                'requires_human_approval',
                'The administrative agent always needs a human to approve the result.',
            )
        return cleaned_data


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
        self.fields['institution'].queryset = institution_choices_for(user)
        # A new consent starts from the least privileged state: the member has
        # to grant the permissions explicitly.
        self.initial.setdefault('status', AIConsent.ConsentStatus.REVOKED)
        self.initial.setdefault('allow_personalization', False)
        self.initial.setdefault('allow_academic_analysis', False)
        self.initial.setdefault('allow_opportunity_matching', False)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('status') == AIConsent.ConsentStatus.GRANTED:
            # A granted consent needs at least one purpose, and it has to be
            # given for an institution.
            if not any(
                cleaned_data.get(flag)
                for flag in (
                    'allow_personalization',
                    'allow_academic_analysis',
                    'allow_opportunity_matching',
                )
            ):
                self.add_error(
                    'status',
                    'Choose at least one purpose before granting consent.',
                )
        return cleaned_data


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
        self.fields['institution'].queryset = institution_choices_for(user)
        self.fields['agent_key'].choices = agent_choices_for_user(user)
        self.user = user

    def clean(self):
        cleaned_data = super().clean()
        agent_key = cleaned_data.get('agent_key')
        if agent_key and agent_key not in dict(agent_choices_for_user(self.user)):
            self.add_error('agent_key', 'You cannot use this agent for your role.')
        return cleaned_data


class AIMessageForm(forms.ModelForm):
    class Meta:
        model = AIMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ask ADOM Institute...'}),
        }
