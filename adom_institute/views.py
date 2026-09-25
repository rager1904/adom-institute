from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import (
    IsInstitutionTeacherOrAdmin,
    is_admin_user,
    is_platform_admin,
    user_can_access_institution,
    user_institution_ids,
)
from .models import AIConsent, AIConversation, AIMessage, AIUsageLedger, AgentTask, KnowledgeDocument
from .agents import list_agent_definitions
from .forms import AIConsentForm, AIConversationForm, AIMessageForm, AgentTaskForm, KnowledgeDocumentForm
from .serializers import (
    AIConsentSerializer,
    AIConversationSerializer,
    AIMessageSerializer,
    AIUsageLedgerSerializer,
    AgentTaskSerializer,
    KnowledgeDocumentSerializer,
)
from .services import KnowledgeIngestionError, ingest_knowledge_document, search_knowledge_chunks


def scoped_institution_queryset(user, queryset, field='institution_id'):
    if is_platform_admin(user):
        return queryset
    institution_ids = user_institution_ids(user)
    if not institution_ids:
        return queryset.none()
    return queryset.filter(**{f'{field}__in': institution_ids})


def ensure_institution_access(user, institution):
    institution_id = getattr(institution, 'id', institution)
    if institution_id and not user_can_access_institution(user, institution_id):
        raise PermissionDenied('You cannot create AI records for this institution.')


class AIConsentViewSet(viewsets.ModelViewSet):
    serializer_class = AIConsentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AIConsent.objects.select_related('user', 'institution')
        if is_admin_user(self.request.user):
            return scoped_institution_queryset(self.request.user, queryset)
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        user = serializer.validated_data.get('user', self.request.user)
        if user != self.request.user and not is_admin_user(self.request.user):
            raise PermissionDenied('You cannot create consent records for another user.')
        ensure_institution_access(self.request.user, serializer.validated_data.get('institution'))
        serializer.save(user=user)


class KnowledgeDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in {'create', 'update', 'partial_update', 'destroy'}:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = KnowledgeDocument.objects.select_related('institution', 'uploaded_by')
        return scoped_institution_queryset(self.request.user, queryset)

    def perform_create(self, serializer):
        ensure_institution_access(self.request.user, serializer.validated_data.get('institution'))
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        document = self.get_object()
        try:
            document = ingest_knowledge_document(document.pk)
        except KnowledgeIngestionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(document)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        try:
            results = search_knowledge_chunks(
                self.get_queryset(),
                request.query_params.get('q', ''),
                request.query_params.get('limit', 10),
            )
        except (KnowledgeIngestionError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'results': results})


class AIConversationViewSet(viewsets.ModelViewSet):
    serializer_class = AIConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AIConversation.objects.select_related('institution', 'user').prefetch_related('messages')
        if is_admin_user(self.request.user):
            return scoped_institution_queryset(self.request.user, queryset)
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        ensure_institution_access(self.request.user, serializer.validated_data.get('institution'))
        serializer.save(user=self.request.user)


class AIMessageViewSet(viewsets.ModelViewSet):
    serializer_class = AIMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AIMessage.objects.select_related('conversation__institution', 'conversation__user')
        if is_admin_user(self.request.user):
            return scoped_institution_queryset(self.request.user, queryset, 'conversation__institution_id')
        return queryset.filter(conversation__user=self.request.user)

    def perform_create(self, serializer):
        conversation = serializer.validated_data['conversation']
        if conversation.user != self.request.user and not is_admin_user(self.request.user):
            raise PermissionDenied('You cannot add messages to this conversation.')
        ensure_institution_access(self.request.user, conversation.institution)
        serializer.save()


class AgentTaskViewSet(viewsets.ModelViewSet):
    serializer_class = AgentTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AgentTask.objects.select_related('institution', 'created_by')
        if is_admin_user(self.request.user):
            return scoped_institution_queryset(self.request.user, queryset)
        return queryset.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        ensure_institution_access(self.request.user, serializer.validated_data.get('institution'))
        serializer.save(created_by=self.request.user)


class AIUsageLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AIUsageLedgerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = AIUsageLedger.objects.select_related('institution', 'user', 'conversation', 'agent_task')
        if is_admin_user(self.request.user):
            return scoped_institution_queryset(self.request.user, queryset)
        return queryset.filter(user=self.request.user)


class AdomInstituteDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'adom_institute/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        documents = scoped_institution_queryset(
            self.request.user,
            KnowledgeDocument.objects.select_related('institution'),
        )
        tasks = AgentTaskViewSet()
        tasks.request = self.request
        task_queryset = tasks.get_queryset()
        context.update({
            'document_count': documents.count(),
            'ready_document_count': documents.filter(processing_status=KnowledgeDocument.ProcessingStatus.READY).count(),
            'task_count': task_queryset.count(),
            'recent_tasks': task_queryset[:5],
            'recent_documents': documents.order_by('-created_at')[:5],
        })
        return context


class KnowledgeDocumentListView(LoginRequiredMixin, ListView):
    model = KnowledgeDocument
    template_name = 'adom_institute/knowledge_document_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        return scoped_institution_queryset(
            self.request.user,
            KnowledgeDocument.objects.select_related('institution', 'uploaded_by'),
        ).order_by('-created_at')


class KnowledgeDocumentCreateView(LoginRequiredMixin, CreateView):
    model = KnowledgeDocument
    form_class = KnowledgeDocumentForm
    template_name = 'adom_institute/knowledge_document_form.html'
    success_url = reverse_lazy('adom_institute:knowledge_document_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        ensure_institution_access(self.request.user, form.cleaned_data.get('institution'))
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, 'Knowledge document uploaded successfully.')
        return super().form_valid(form)


class KnowledgeDocumentDetailView(LoginRequiredMixin, DetailView):
    model = KnowledgeDocument
    template_name = 'adom_institute/knowledge_document_detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return scoped_institution_queryset(
            self.request.user,
            KnowledgeDocument.objects.select_related('institution', 'uploaded_by').prefetch_related('chunks'),
        )


class KnowledgeDocumentProcessView(LoginRequiredMixin, View):
    def post(self, request, pk):
        document = get_object_or_404(scoped_institution_queryset(
            request.user,
            KnowledgeDocument.objects.all(),
        ), pk=pk)
        try:
            ingest_knowledge_document(document.pk)
            messages.success(request, 'Knowledge document processed successfully.')
        except KnowledgeIngestionError as exc:
            messages.error(request, str(exc))
        return redirect(reverse('adom_institute:knowledge_document_detail', kwargs={'pk': pk}))


class KnowledgeSearchView(LoginRequiredMixin, TemplateView):
    template_name = 'adom_institute/knowledge_search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()
        documents = scoped_institution_queryset(self.request.user, KnowledgeDocument.objects.all())
        results = []
        error = ''
        if query:
            try:
                results = search_knowledge_chunks(documents, query)
            except (KnowledgeIngestionError, ValueError) as exc:
                error = str(exc)
        context.update({'query': query, 'results': results, 'error': error})
        return context


class AgentCatalogView(LoginRequiredMixin, TemplateView):
    template_name = 'adom_institute/agent_catalog.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agents'] = list_agent_definitions()
        return context


class AgentTaskListView(LoginRequiredMixin, ListView):
    model = AgentTask
    template_name = 'adom_institute/agent_task_list.html'
    context_object_name = 'tasks'
    paginate_by = 20

    def get_queryset(self):
        viewset = AgentTaskViewSet()
        viewset.request = self.request
        return viewset.get_queryset().order_by('-created_at')


class AgentTaskCreateView(LoginRequiredMixin, CreateView):
    model = AgentTask
    form_class = AgentTaskForm
    template_name = 'adom_institute/agent_task_form.html'
    success_url = reverse_lazy('adom_institute:agent_task_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        ensure_institution_access(self.request.user, form.cleaned_data.get('institution'))
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Agent task queued successfully.')
        return super().form_valid(form)


class AgentTaskDetailView(LoginRequiredMixin, DetailView):
    model = AgentTask
    template_name = 'adom_institute/agent_task_detail.html'
    context_object_name = 'task'

    def get_queryset(self):
        viewset = AgentTaskViewSet()
        viewset.request = self.request
        return viewset.get_queryset()


class UsageLedgerListView(LoginRequiredMixin, ListView):
    model = AIUsageLedger
    template_name = 'adom_institute/usage_ledger_list.html'
    context_object_name = 'usage_entries'
    paginate_by = 20

    def get_queryset(self):
        viewset = AIUsageLedgerViewSet()
        viewset.request = self.request
        return viewset.get_queryset().order_by('-created_at')


class AIConsentListView(LoginRequiredMixin, ListView):
    model = AIConsent
    template_name = 'adom_institute/consent_list.html'
    context_object_name = 'consents'

    def get_queryset(self):
        viewset = AIConsentViewSet()
        viewset.request = self.request
        return viewset.get_queryset().order_by('-granted_at')


class AIConsentCreateView(LoginRequiredMixin, CreateView):
    model = AIConsent
    form_class = AIConsentForm
    template_name = 'adom_institute/consent_form.html'
    success_url = reverse_lazy('adom_institute:consent_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        ensure_institution_access(self.request.user, form.cleaned_data.get('institution'))
        form.instance.user = self.request.user
        messages.success(self.request, 'AI consent preferences saved.')
        return super().form_valid(form)


class AIConversationListView(LoginRequiredMixin, ListView):
    model = AIConversation
    template_name = 'adom_institute/conversation_list.html'
    context_object_name = 'conversations'
    paginate_by = 20

    def get_queryset(self):
        viewset = AIConversationViewSet()
        viewset.request = self.request
        return viewset.get_queryset().order_by('-updated_at')


class AIConversationCreateView(LoginRequiredMixin, CreateView):
    model = AIConversation
    form_class = AIConversationForm
    template_name = 'adom_institute/conversation_form.html'
    success_url = reverse_lazy('adom_institute:conversation_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        ensure_institution_access(self.request.user, form.cleaned_data.get('institution'))
        form.instance.user = self.request.user
        messages.success(self.request, 'Conversation created.')
        return super().form_valid(form)


class AIConversationDetailView(LoginRequiredMixin, DetailView):
    model = AIConversation
    template_name = 'adom_institute/conversation_detail.html'
    context_object_name = 'conversation'

    def get_queryset(self):
        viewset = AIConversationViewSet()
        viewset.request = self.request
        return viewset.get_queryset().prefetch_related('messages')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message_form'] = AIMessageForm()
        return context


class AIMessageCreateView(LoginRequiredMixin, CreateView):
    model = AIMessage
    form_class = AIMessageForm

    def form_valid(self, form):
        viewset = AIConversationViewSet()
        viewset.request = self.request
        conversation = get_object_or_404(viewset.get_queryset(), pk=self.kwargs['pk'])
        form.instance.conversation = conversation
        form.instance.role = AIMessage.MessageRole.USER
        messages.success(self.request, 'Message added to the conversation.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('adom_institute:conversation_detail', kwargs={'pk': self.kwargs['pk']})


class OpportunityHubView(LoginRequiredMixin, TemplateView):
    template_name = 'adom_institute/opportunity_hub.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        viewset = AgentTaskViewSet()
        viewset.request = self.request
        context['opportunity_tasks'] = viewset.get_queryset().filter(
            agent_key='scholarship_opportunities'
        ).order_by('-created_at')[:10]
        return context
