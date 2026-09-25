from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token

from .models import User, UserProfile, Role, Permission
from .models import Institution, InstitutionMembership
from .permissions import (
    IsPlatformOrInstitutionAdmin, active_memberships, has_institution_admin_role,
    is_platform_admin, user_institution_ids
)
from .serializers import (
    InstitutionSerializer, InstitutionMembershipSerializer, UserSerializer,
    UserProfileSerializer, RoleSerializer, PermissionSerializer
)
from .forms import (
    InstitutionRegistrationForm, TeacherRegistrationForm, UserRegistrationForm,
    UserProfileForm
)
from .dashboard_services import build_dashboard_context
from adom_institute.agents import list_agent_definitions
from adom_institute.models import AIConversation, AIUsageLedger, AgentTask, KnowledgeDocument
from adom_institute.rag import get_rag_blueprint
from adom_institute.registry import get_ai_runtime_config, list_supported_model_profiles
from students.models import Class, Student
from teachers.models import Teacher


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if is_platform_admin(self.request.user):
            return User.objects.all()
        institution_ids = user_institution_ids(self.request.user)
        if has_institution_admin_role(self.request.user) and institution_ids:
            return User.objects.filter(
                institution_memberships__institution_id__in=institution_ids,
                institution_memberships__is_active=True,
            ).distinct()
        return User.objects.filter(id=self.request.user.id)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if is_platform_admin(self.request.user):
            return UserProfile.objects.all()
        institution_ids = user_institution_ids(self.request.user)
        if has_institution_admin_role(self.request.user) and institution_ids:
            return UserProfile.objects.filter(
                user__institution_memberships__institution_id__in=institution_ids,
                user__institution_memberships__is_active=True,
            ).distinct()
        return UserProfile.objects.filter(user=self.request.user)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsPlatformOrInstitutionAdmin]


class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsPlatformOrInstitutionAdmin]


class InstitutionViewSet(viewsets.ModelViewSet):
    serializer_class = InstitutionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if is_platform_admin(self.request.user):
            return Institution.objects.all()
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids:
            return Institution.objects.filter(id__in=institution_ids, is_active=True)
        return Institution.objects.none()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()


class InstitutionMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = InstitutionMembershipSerializer
    permission_classes = [IsPlatformOrInstitutionAdmin]

    def get_queryset(self):
        queryset = InstitutionMembership.objects.select_related('institution', 'user', 'assigned_by')
        if is_platform_admin(self.request.user):
            return queryset
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids:
            return queryset.filter(institution_id__in=institution_ids)
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email,
            'user_type': user.user_type
        })


# Web Views
class HomeView(TemplateView):
    template_name = 'home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_count = len(list_agent_definitions())
        context['platform_stats'] = [
            {
                'value': Institution.objects.filter(is_active=True).count(),
                'label': 'Active institutions',
                'detail': 'Schools, colleges, and universities',
            },
            {
                'value': Student.objects.filter(is_active=True).count(),
                'label': 'Active students',
                'detail': 'Learners managed in ADOM Institute',
            },
            {
                'value': Teacher.objects.filter(employment_status=Teacher.EmploymentStatus.ACTIVE).count(),
                'label': 'Active teachers',
                'detail': 'Teaching staff and academic teams',
            },
            {
                'value': Class.objects.filter(is_active=True).count(),
                'label': 'Active classes',
                'detail': 'Current learning cohorts',
            },
            {
                'value': agent_count,
                'label': 'Open-source AI agents',
                'detail': 'Including ECZ and opportunities agents',
            },
        ]
        context['modules'] = [
            {'name': 'Student Information', 'icon': 'fa-user-graduate', 'text': 'Admissions, profiles, parents, classes, and academic records.'},
            {'name': 'Learning Management', 'icon': 'fa-book-open-reader', 'text': 'Assignments, exams, resources, progress, and teacher workflows.'},
            {'name': 'Institution Operations', 'icon': 'fa-school', 'text': 'Attendance, fees, communication, timetables, library, and analytics.'},
            {'name': 'Open-Source AI', 'icon': 'fa-robot', 'text': 'Curriculum, tutoring, scholarships, risk detection, and research agents.'},
        ]
        return context


class AIHubView(TemplateView):
    template_name = 'accounts/ai_hub.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        institution_ids = user_institution_ids(user)
        knowledge_documents = KnowledgeDocument.objects.all()
        conversations = AIConversation.objects.all()
        agent_tasks = AgentTask.objects.select_related('institution', 'created_by')
        usage_entries = AIUsageLedger.objects.all()

        if not is_platform_admin(user):
            if institution_ids:
                knowledge_documents = knowledge_documents.filter(institution_id__in=institution_ids)
                agent_tasks = agent_tasks.filter(institution_id__in=institution_ids)
                conversations = conversations.filter(institution_id__in=institution_ids)
                usage_entries = usage_entries.filter(institution_id__in=institution_ids)
            else:
                knowledge_documents = knowledge_documents.none()
                agent_tasks = agent_tasks.filter(created_by=user)
                conversations = conversations.filter(user=user)
                usage_entries = usage_entries.filter(user=user)

        if not has_institution_admin_role(user):
            conversations = conversations.filter(user=user)
            agent_tasks = agent_tasks.filter(created_by=user)
            usage_entries = usage_entries.filter(user=user)

        context['runtime'] = get_ai_runtime_config()
        context['model_profiles'] = list_supported_model_profiles()
        context['agents'] = list_agent_definitions()
        context['rag'] = get_rag_blueprint()
        context['ai_stats'] = [
            {
                'label': 'Knowledge Documents',
                'value': knowledge_documents.count(),
                'icon': 'fa-file-lines',
                'detail': 'Institution-scoped RAG sources',
            },
            {
                'label': 'Conversations',
                'value': conversations.count(),
                'icon': 'fa-comments',
                'detail': 'ADOM Institute conversation records',
            },
            {
                'label': 'Agent Tasks',
                'value': agent_tasks.count(),
                'icon': 'fa-diagram-project',
                'detail': 'Queued and completed agent work',
            },
            {
                'label': 'Usage Entries',
                'value': usage_entries.count(),
                'icon': 'fa-gauge-high',
                'detail': 'Open-source model activity logs',
            },
        ]
        context['recent_agent_tasks'] = agent_tasks.order_by('-created_at')[:5]
        return context


class DashboardView(TemplateView):
    template_name = 'accounts/dashboard.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['dashboard'] = build_dashboard_context(user)
        
        # Add user-specific data based on user type
        if user.is_student:
            context['student_data'] = getattr(user, 'student_profile', None)
        elif user.is_teacher:
            context['teacher_data'] = getattr(user, 'teacher_profile', None)
        elif user.is_parent:
            context['parent_data'] = getattr(user, 'parent_profile', None)
        
        return context


class LoginView(TemplateView):
    template_name = 'accounts/login.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
            return self.get(request, *args, **kwargs)


class LogoutView(TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('accounts:login')


class RegisterView(CreateView):
    template_name = 'accounts/register.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Registration successful! Please log in.')
        return response


class TeacherRegisterView(CreateView):
    template_name = 'accounts/register_teacher.html'
    form_class = TeacherRegistrationForm
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Teacher registration successful! Please log in.')
        return response


class InstitutionRegisterView(CreateView):
    template_name = 'accounts/register_institution.html'
    form_class = InstitutionRegistrationForm
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Institution registration successful! Please log in as the owner account.')
        return response


class ProfileView(UpdateView):
    template_name = 'accounts/profile_modern.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('accounts:profile')
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Profile updated successfully!')
        return response
