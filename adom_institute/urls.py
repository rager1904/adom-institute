from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AIConsentViewSet,
    AIConsentCreateView,
    AIConsentListView,
    AIConversationCreateView,
    AIConversationDetailView,
    AIConversationListView,
    AIConversationViewSet,
    AIMessageViewSet,
    AIMessageCreateView,
    AIUsageLedgerViewSet,
    AgentCatalogView,
    AgentTaskCreateView,
    AgentTaskDetailView,
    AgentTaskListView,
    AgentTaskViewSet,
    AdomInstituteDashboardView,
    KnowledgeDocumentViewSet,
    KnowledgeDocumentListView,
    KnowledgeDocumentCreateView,
    KnowledgeDocumentDetailView,
    KnowledgeDocumentProcessView,
    KnowledgeSearchView,
    OpportunityHubView,
    UsageLedgerListView,
)

router = DefaultRouter()
router.register(r'consents', AIConsentViewSet, basename='ai-consent')
router.register(r'knowledge-documents', KnowledgeDocumentViewSet, basename='knowledge-document')
router.register(r'conversations', AIConversationViewSet, basename='ai-conversation')
router.register(r'messages', AIMessageViewSet, basename='ai-message')
router.register(r'agent-tasks', AgentTaskViewSet, basename='agent-task')
router.register(r'usage-ledger', AIUsageLedgerViewSet, basename='ai-usage-ledger')

app_name = 'adom_institute'

urlpatterns = [
    path('', AdomInstituteDashboardView.as_view(), name='dashboard'),
    path('knowledge/', KnowledgeDocumentListView.as_view(), name='knowledge_document_list'),
    path('knowledge/upload/', KnowledgeDocumentCreateView.as_view(), name='knowledge_document_create'),
    path('knowledge/<int:pk>/', KnowledgeDocumentDetailView.as_view(), name='knowledge_document_detail'),
    path('knowledge/<int:pk>/process/', KnowledgeDocumentProcessView.as_view(), name='knowledge_document_process'),
    path('knowledge/search/', KnowledgeSearchView.as_view(), name='knowledge_search'),
    path('agents/', AgentCatalogView.as_view(), name='agent_catalog'),
    path('tasks/', AgentTaskListView.as_view(), name='agent_task_list'),
    path('tasks/create/', AgentTaskCreateView.as_view(), name='agent_task_create'),
    path('tasks/<int:pk>/', AgentTaskDetailView.as_view(), name='agent_task_detail'),
    path('usage/', UsageLedgerListView.as_view(), name='usage_ledger_list'),
    path('consent/', AIConsentListView.as_view(), name='consent_list'),
    path('consent/create/', AIConsentCreateView.as_view(), name='consent_create'),
    path('conversations/', AIConversationListView.as_view(), name='conversation_list'),
    path('conversations/create/', AIConversationCreateView.as_view(), name='conversation_create'),
    path('conversations/<int:pk>/', AIConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/<int:pk>/messages/create/', AIMessageCreateView.as_view(), name='message_create'),
    path('opportunities/', OpportunityHubView.as_view(), name='opportunity_hub'),
    path('api/', include(router.urls)),
]
