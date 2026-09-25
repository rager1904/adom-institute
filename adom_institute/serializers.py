from rest_framework import serializers

from .agents import AGENT_DEFINITIONS
from .models import AIConsent, AIConversation, AIMessage, AIUsageLedger, AgentTask, KnowledgeDocument
from .rag import KNOWLEDGE_SOURCE_TYPES


class AIConsentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = AIConsent
        fields = [
            'id', 'user', 'user_name', 'institution', 'status', 'allow_personalization',
            'allow_academic_analysis', 'allow_opportunity_matching', 'granted_at',
            'revoked_at', 'policy_version',
        ]
        read_only_fields = ['granted_at', 'revoked_at']


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = [
            'id', 'institution', 'uploaded_by', 'uploaded_by_name', 'title', 'source_type',
            'subject', 'grade_level', 'access_scope', 'file', 'checksum',
            'processing_status', 'metadata', 'error_message', 'created_at', 'updated_at',
        ]
        read_only_fields = ['uploaded_by', 'checksum', 'processing_status', 'error_message', 'created_at', 'updated_at']

    def validate_source_type(self, value):
        if value not in {source.key for source in KNOWLEDGE_SOURCE_TYPES}:
            raise serializers.ValidationError('Unsupported knowledge source type.')
        return value


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ['id', 'conversation', 'role', 'content', 'model_name', 'citations', 'token_count', 'created_at']
        read_only_fields = ['created_at']


class AIConversationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields = [
            'id', 'institution', 'user', 'user_name', 'agent_key', 'title', 'status',
            'messages', 'created_at', 'updated_at',
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def validate_agent_key(self, value):
        if value not in AGENT_DEFINITIONS:
            raise serializers.ValidationError('Unsupported AI agent.')
        return value


class AgentTaskSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = AgentTask
        fields = [
            'id', 'institution', 'created_by', 'created_by_name', 'agent_key', 'status',
            'model_profile', 'input_payload', 'output_payload', 'error_message',
            'requires_human_approval', 'created_at', 'started_at', 'completed_at',
        ]
        read_only_fields = [
            'created_by', 'status', 'output_payload', 'error_message', 'started_at',
            'completed_at', 'created_at',
        ]

    def validate_agent_key(self, value):
        if value not in AGENT_DEFINITIONS:
            raise serializers.ValidationError('Unsupported AI agent.')
        return value


class AIUsageLedgerSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = AIUsageLedger
        fields = [
            'id', 'institution', 'user', 'user_name', 'conversation', 'agent_task',
            'provider', 'model_name', 'prompt_tokens', 'completion_tokens', 'total_tokens',
            'latency_ms', 'estimated_cost', 'metadata', 'created_at',
        ]
        read_only_fields = ['created_at']
