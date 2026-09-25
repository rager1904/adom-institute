from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Institution, User
from accounts.validators import document_upload_validators
from .agents import AGENT_DEFINITIONS
from .rag import KNOWLEDGE_SOURCE_TYPES


def agent_choices():
    return [(key, definition.name) for key, definition in AGENT_DEFINITIONS.items()]


def source_type_choices():
    return [(source.key, source.description) for source in KNOWLEDGE_SOURCE_TYPES]


class AIConsent(models.Model):
    class ConsentStatus(models.TextChoices):
        GRANTED = 'granted', _('Granted')
        REVOKED = 'revoked', _('Revoked')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_consents')
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='ai_consents', null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=ConsentStatus.choices, default=ConsentStatus.GRANTED)
    allow_personalization = models.BooleanField(default=True)
    allow_academic_analysis = models.BooleanField(default=True)
    allow_opportunity_matching = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=50, default='2026-06')

    class Meta:
        db_table = 'adom_institute_consent'
        unique_together = ('user', 'institution', 'policy_version')
        indexes = [
            models.Index(fields=['user', 'status'], name='adom_consent_user_idx'),
            models.Index(fields=['institution', 'status'], name='adom_consent_inst_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.status}'


class KnowledgeDocument(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SCANNING = 'scanning', _('Scanning')
        OCR = 'ocr', _('OCR')
        INDEXING = 'indexing', _('Indexing')
        READY = 'ready', _('Ready')
        REJECTED = 'rejected', _('Rejected')
        FAILED = 'failed', _('Failed')

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='knowledge_documents')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_knowledge_documents')
    title = models.CharField(max_length=255)
    source_type = models.CharField(max_length=50, choices=source_type_choices())
    subject = models.CharField(max_length=100, blank=True)
    grade_level = models.CharField(max_length=50, blank=True)
    access_scope = models.CharField(max_length=100, default='institution')
    file = models.FileField(upload_to='knowledge/', validators=document_upload_validators)
    checksum = models.CharField(max_length=128, blank=True)
    processing_status = models.CharField(
        max_length=20, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING
    )
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'adom_institute_knowledge_document'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'source_type'], name='adom_institute_doc_source_idx'),
            models.Index(fields=['institution', 'processing_status'], name='adom_institute_doc_status_idx'),
        ]

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    page_number = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True)
    embedding_vector = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adom_institute_knowledge_chunk'
        unique_together = ('document', 'chunk_index')
        ordering = ['document_id', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index'], name='adom_institute_chunk_doc_idx'),
        ]

    def __str__(self):
        return f'{self.document_id}:{self.chunk_index}'


class AIConversation(models.Model):
    class ConversationStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        ARCHIVED = 'archived', _('Archived')

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='ai_conversations', null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_conversations')
    agent_key = models.CharField(max_length=80, choices=agent_choices(), default='learning_coach')
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=ConversationStatus.choices, default=ConversationStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'adom_institute_conversation'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['institution', 'agent_key', 'updated_at'], name='adom_institute_conv_agent_idx'),
            models.Index(fields=['user', 'updated_at'], name='adom_institute_conv_user_idx'),
        ]

    def __str__(self):
        return self.title


class AIMessage(models.Model):
    class MessageRole(models.TextChoices):
        USER = 'user', _('User')
        ASSISTANT = 'assistant', _('Assistant')
        SYSTEM = 'system', _('System')
        TOOL = 'tool', _('Tool')

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=MessageRole.choices)
    content = models.TextField()
    model_name = models.CharField(max_length=120, blank=True)
    citations = models.JSONField(default=list, blank=True)
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adom_institute_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at'], name='adom_institute_msg_conv_idx'),
        ]

    def __str__(self):
        return f'{self.conversation_id} - {self.role}'


class AgentTask(models.Model):
    class TaskStatus(models.TextChoices):
        QUEUED = 'queued', _('Queued')
        RUNNING = 'running', _('Running')
        WAITING_APPROVAL = 'waiting_approval', _('Waiting Approval')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')

    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='ai_agent_tasks', null=True, blank=True
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ai_agent_tasks')
    agent_key = models.CharField(max_length=80, choices=agent_choices())
    status = models.CharField(max_length=30, choices=TaskStatus.choices, default=TaskStatus.QUEUED)
    model_profile = models.CharField(max_length=50, default='chat')
    input_payload = models.JSONField(default=dict)
    output_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    requires_human_approval = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'adom_institute_agent_task'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'agent_key', 'status'], name='adom_institute_task_agent_idx'),
            models.Index(fields=['created_by', 'created_at'], name='adom_institute_task_user_idx'),
        ]

    def __str__(self):
        return f'{self.agent_key} - {self.status}'


class AIUsageLedger(models.Model):
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name='ai_usage_entries', null=True, blank=True
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ai_usage_entries')
    conversation = models.ForeignKey(
        AIConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='usage_entries'
    )
    agent_task = models.ForeignKey(
        AgentTask, on_delete=models.SET_NULL, null=True, blank=True, related_name='usage_entries'
    )
    provider = models.CharField(max_length=80, default='ollama')
    model_name = models.CharField(max_length=120)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'adom_institute_usage_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'created_at'], name='adom_institute_usage_inst_idx'),
            models.Index(fields=['user', 'created_at'], name='adom_institute_usage_user_idx'),
            models.Index(fields=['provider', 'model_name'], name='adom_institute_usage_model_idx'),
        ]

    def __str__(self):
        return f'{self.model_name} - {self.total_tokens} tokens'
