from django.contrib import admin

from .models import (
    AIConsent,
    AIConversation,
    AIMessage,
    AIUsageLedger,
    AgentTask,
    KnowledgeChunk,
    KnowledgeDocument,
)


@admin.register(AIConsent)
class AIConsentAdmin(admin.ModelAdmin):
    list_display = ('user', 'institution', 'status', 'policy_version', 'granted_at')
    list_filter = ('status', 'policy_version', 'institution')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'institution', 'source_type', 'processing_status', 'created_at')
    list_filter = ('source_type', 'processing_status', 'institution')
    search_fields = ('title', 'subject', 'grade_level')


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ('document', 'chunk_index', 'page_number', 'embedding_model')
    search_fields = ('document__title', 'content')


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'institution', 'agent_key', 'status', 'updated_at')
    list_filter = ('agent_key', 'status', 'institution')
    search_fields = ('title', 'user__email')
    inlines = [AIMessageInline]


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ('agent_key', 'institution', 'created_by', 'status', 'requires_human_approval', 'created_at')
    list_filter = ('agent_key', 'status', 'requires_human_approval', 'institution')
    search_fields = ('created_by__email', 'error_message')


@admin.register(AIUsageLedger)
class AIUsageLedgerAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'provider', 'institution', 'user', 'total_tokens', 'latency_ms', 'created_at')
    list_filter = ('provider', 'model_name', 'institution')
    search_fields = ('user__email', 'model_name')
