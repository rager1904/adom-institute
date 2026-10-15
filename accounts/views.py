from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, DetailView,
)
from django.contrib import messages
from django.urls import reverse, reverse_lazy
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
    UserProfileForm, InstitutionProfileForm, InstitutionSearchForm,
    OnboardingAcademicYearForm, OnboardingClassForm, OnboardingFeeCategoryForm,
    OnboardingFeeStructureForm,
)
from .dashboard_services import build_dashboard_context
from adom_institute.agents import list_agent_definitions
from students.models import AcademicYear, Class, Student
from teachers.models import Teacher
from fees.models import FeeCategory, FeeStructure


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


class PublicPageView(TemplateView):
    """Public marketing and legal information pages for the landing site."""
    template_name = 'public_page.html'

    PAGES = {
        'about': {
            'title': 'About ADOM Institute',
            'eyebrow': 'Education • Training • Educational Supplies',
            'intro': 'Empowering education, skills and innovation.',
            'summary': 'ADOM Institute is a Zambian education, training and educational supplies institution committed to empowering learners, professionals, entrepreneurs and schools through accessible education and practical skills development.',
            'sections': [
                ('Who we are', 'We offer professional and vocational short courses, academic tuition, educational books, computers, ICT equipment and customised solutions for schools and businesses.'),
                ('What we teach', "Our programmes focus on developing practical knowledge in artificial intelligence, information technology, finance, accounting, entrepreneurship and other essential skills for today's changing world."),
                ('Supporting institutions', 'We also support educational institutions through the supply of curriculum-aligned learning materials, computer laboratory development, school library resources and ICT solutions, as well as the ADOM education management dashboard that brings learner records, classes, attendance, assessments, fees, communication and library resources into one connected workspace.'),
                ('Our Vision', 'To become a trusted centre of excellence in practical education, digital innovation and educational resources in Zambia and beyond.'),
                ('Our Mission', 'To empower individuals and institutions through quality learning, relevant skills, accessible educational materials and innovative technology solutions.'),
                ('Our Motto', 'Learn Today • Lead Tomorrow.'),
            ],
        },
        'privacy': {
            'title': 'Privacy at ADOM Institute',
            'eyebrow': 'Privacy and responsible data use',
            'intro': 'School information deserves careful handling.',
            'summary': 'ADOM Institute processes account and education information to provide school management features. Each institution is responsible for its lawful use of the platform and for deciding which staff members may access its records.',
            'sections': [
                ('Information used to provide the service', 'Depending on the features an institution uses, the platform may store account details, learner and staff records, attendance, academic activity, fee records, messages, and uploaded school documents.'),
                ('Access and security', 'Access is provided through authenticated accounts and role-based permissions. Institutions should assign accounts carefully, keep credentials private, and promptly remove access when a person no longer needs it.'),
                ('AI-supported features', 'When an institution enables AI tools, submitted prompts and selected school content may be processed to provide a response. Avoid submitting sensitive personal information unless the institution has approved that use and appropriate safeguards are in place.'),
                ('Questions and requests', 'For questions about a school record, contact the institution that manages it. For platform privacy questions, contact the ADOM Institute team using the contact details provided by your institution.'),
            ],
        },
        'terms': {
            'title': 'Terms of use',
            'eyebrow': 'Using the platform',
            'intro': 'Clear expectations for a shared school workspace.',
            'summary': 'These terms describe the basic expectations for using the ADOM Institute website and platform. Institutions may also have separate service or data-processing agreements that govern their use.',
            'sections': [
                ('Use accounts responsibly', 'Use only accounts assigned to you, protect your login credentials, and keep profile information accurate. Do not attempt to access records or features beyond your assigned permissions.'),
                ('Respect school information', 'Use platform information only for legitimate education and administration purposes. Do not disclose learner, family, or staff information to people who are not authorized to receive it.'),
                ('Content and availability', 'Institutions remain responsible for the information they enter and the permissions they configure. Features may change as the platform is maintained and improved; critical school records should follow the institution’s backup and retention procedures.'),
                ('Questions', 'If you believe an account or record has been accessed improperly, notify your institution administrator promptly so they can review access and take appropriate action.'),
            ],
        },
        'contact': {
            'title': 'Contact ADOM Institute',
            'eyebrow': 'Start a conversation',
            'intro': 'Let’s make school operations clearer.',
            'summary': 'Interested in bringing ADOM Institute to your school? Your institution can register to explore the platform or contact its platform administrator for support with an existing account.',
            'sections': [
                ('For schools exploring ADOM', 'Use the institution registration link to begin setting up your school. A school administrator can then invite the right staff and configure the features your team needs.'),
                ('For current users', 'For password, access, learner-record, or fee questions, contact your school administrator first. They can verify your identity and route the request to the right team.'),
                ('For platform questions', 'For partnership and platform enquiries, contact your institution’s ADOM representative or use the registration page to leave your school details.'),
            ],
        },
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_key = self.kwargs['page']
        page = self.PAGES[page_key]
        title = page['title']
        if 'ADOM Institute' not in title:
            title = f'{title} | ADOM Institute'
        context['page'] = page
        context['page_key'] = page_key
        context['seo_title'] = title
        return context


def institution_pending_gate(user):
    """Return the institution blocking access for an admin whose tenant is not
    yet approved, or ``None`` when the user may proceed normally."""
    if not user or not user.is_authenticated:
        return None
    if is_platform_admin(user) or user.is_superuser:
        return None
    memberships = user.institution_memberships.filter(
        is_active=True,
    ).select_related('institution')
    admin_roles = {
        InstitutionMembership.MembershipRole.OWNER,
        InstitutionMembership.MembershipRole.ADMINISTRATOR,
    }
    has_admin_membership = (
        user.user_type == 'administrator'
        or memberships.filter(role__in=admin_roles).exists()
    )
    if not has_admin_membership:
        return None
    if memberships.filter(
        institution__status=Institution.Status.APPROVED,
        institution__is_active=True,
    ).exists():
        return None
    blocking = memberships.exclude(
        institution__status=Institution.Status.APPROVED,
    ).first()
    return blocking.institution if blocking else None


class PlatformAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return is_platform_admin(self.request.user)


class DashboardView(TemplateView):
    template_name = 'accounts/dashboard.html'
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        blocking_institution = institution_pending_gate(self.request.user)
        if blocking_institution is not None:
            return redirect('accounts:institution_status')
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['dashboard'] = build_dashboard_context(user)

        if is_platform_admin(user):
            context['pending_institutions'] = Institution.objects.filter(
                status=Institution.Status.PENDING
            ).order_by('-created_at')[:10]

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
        return redirect('home')


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
    success_url = reverse_lazy('accounts:institution_submitted')

    def form_valid(self, form):
        response = super().form_valid(form)
        institution = getattr(form, 'institution', None)
        if institution is not None:
            self.notify_admins(institution)
        messages.success(
            self.request,
            'Institution registration submitted. We will review your application and email you once it is approved.',
        )
        return response

    @staticmethod
    def notify_admins(institution):
        from communication.notifications import notify_platform_admins

        notify_platform_admins(
            title='New institution awaiting approval',
            message=f'{institution.name} submitted a registration and needs review.',
            url=reverse('accounts:institution_detail', args=[institution.pk]),
            action_label='Review',
            is_urgent=True,
        )


class InstitutionSubmittedView(TemplateView):
    template_name = 'accounts/institution_submitted.html'


class InstitutionStatusView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/institution_status.html'

    def dispatch(self, request, *args, **kwargs):
        self.institution = None
        if request.user.is_authenticated:
            self.institution = institution_pending_gate(request.user)
            if self.institution is None:
                return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['institution'] = self.institution
        return context


class PlatformInstitutionListView(PlatformAdminRequiredMixin, ListView):
    model = Institution
    template_name = 'accounts/institution_list.html'
    context_object_name = 'institutions'
    paginate_by = 20

    def get_queryset(self):
        queryset = Institution.objects.annotate(
            member_count=Count('memberships', distinct=True),
        )
        self.search_form = InstitutionSearchForm(self.request.GET)
        if self.search_form.is_valid():
            q = (self.search_form.cleaned_data.get('q') or '').strip()
            status_filter = self.search_form.cleaned_data.get('status')
            if q:
                queryset = queryset.filter(
                    Q(name__icontains=q) | Q(code__icontains=q) | Q(email__icontains=q)
                )
            if status_filter:
                queryset = queryset.filter(status=status_filter)
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        context['pending_count'] = Institution.objects.filter(
            status=Institution.Status.PENDING
        ).count()
        context['status_choices'] = Institution.Status.choices
        return context


class PlatformInstitutionDetailView(PlatformAdminRequiredMixin, DetailView):
    model = Institution
    template_name = 'accounts/institution_detail.html'
    context_object_name = 'institution'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution = self.object
        context['memberships'] = institution.memberships.select_related('user').order_by('role', 'user__first_name')
        context['academic_years'] = institution.academic_years.order_by('-start_date')
        context['classes'] = Class.objects.filter(
            academic_year__institution=institution
        ).select_related('academic_year').order_by('display_name')[:50]
        context['student_count'] = Student.objects.filter(
            current_class__academic_year__institution=institution,
            is_active=True,
        ).count()
        context['teacher_count'] = Teacher.objects.filter(
            user__institution_memberships__institution=institution,
        ).distinct().count()
        context['fee_structure_count'] = FeeStructure.objects.filter(
            academic_year__institution=institution,
        ).count()
        return context


@login_required
@user_passes_test(is_platform_admin, login_url='accounts:login')
@require_POST
def institution_approve(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    institution.approve(approved_by=request.user)
    _notify_institution_decision(
        institution,
        title='Institution approved',
        message=f'{institution.name} has been approved. You can now complete setup and start adding records.',
        url=reverse('accounts:onboarding'),
        action_label='Set up',
    )
    messages.success(request, f'{institution.name} has been approved.')
    return redirect('accounts:institution_detail', pk=pk)


@login_required
@user_passes_test(is_platform_admin, login_url='accounts:login')
@require_POST
def institution_reject(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    reason = (request.POST.get('reason') or '').strip()
    institution.reject(reason=reason, approved_by=request.user)
    message = f'The registration for {institution.name} was not approved.'
    if reason:
        message = f'{message} Reason: {reason}'
    _notify_institution_decision(
        institution,
        title='Registration not approved',
        message=message,
        url=reverse('accounts:institution_status'),
        action_label='View',
        is_urgent=True,
    )
    messages.warning(request, f'{institution.name} has been rejected.')
    return redirect('accounts:institution_detail', pk=pk)


@login_required
@user_passes_test(is_platform_admin, login_url='accounts:login')
@require_POST
def institution_suspend(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    institution.status = Institution.Status.SUSPENDED
    institution.is_active = False
    institution.save(update_fields=['status', 'is_active', 'updated_at'])
    _notify_institution_decision(
        institution,
        title='Institution suspended',
        message=f'Access for {institution.name} has been suspended. Contact support for more information.',
        url=reverse('accounts:institution_status'),
        action_label='View',
        is_urgent=True,
    )
    messages.warning(request, f'{institution.name} has been suspended.')
    return redirect('accounts:institution_detail', pk=pk)


@login_required
@user_passes_test(is_platform_admin, login_url='accounts:login')
@require_POST
def institution_reactivate(request, pk):
    institution = get_object_or_404(Institution, pk=pk)
    institution.approve(approved_by=request.user)
    _notify_institution_decision(
        institution,
        title='Institution reactivated',
        message=f'Access for {institution.name} has been restored.',
        url=reverse('accounts:dashboard'),
        action_label='Open',
    )
    messages.success(request, f'{institution.name} has been reactivated.')
    return redirect('accounts:institution_detail', pk=pk)


def _notify_institution_decision(institution, *, title, message, url='', action_label='', is_urgent=False):
    """Notify an institution's administrators about an approval decision."""
    from communication.notifications import notify_institution_admins

    notify_institution_admins(
        institution,
        title=title,
        message=message,
        url=url,
        action_label=action_label,
        is_urgent=is_urgent,
    )


class InstitutionOnboardingView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/onboarding.html'
    STEPS = ['profile', 'academic_year', 'class', 'fee_category', 'fee_structure', 'done']
    STEP_TITLES = {
        'profile': 'School profile',
        'academic_year': 'Academic year',
        'class': 'Classes',
        'fee_category': 'Fee categories',
        'fee_structure': 'Fee structure',
        'done': 'Finish',
    }

    def get_institution(self):
        memberships = self.request.user.institution_memberships.select_related('institution')
        admin_roles = {
            InstitutionMembership.MembershipRole.OWNER,
            InstitutionMembership.MembershipRole.ADMINISTRATOR,
        }
        membership = (
            memberships.filter(role__in=admin_roles).first()
            or memberships.first()
        )
        return membership.institution if membership else None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.institution = self.get_institution()
        if self.institution is None:
            messages.info(request, 'You are not linked to an institution to set up.')
            return redirect('accounts:dashboard')
        if self.institution.status != Institution.Status.APPROVED:
            return redirect('accounts:institution_status')
        return super().dispatch(request, *args, **kwargs)

    def get_step(self):
        step = self.request.POST.get('step') or self.request.GET.get('step') or 'profile'
        if step not in self.STEPS:
            step = 'profile'
        return step

    def get_form(self, step):
        institution = self.institution
        data = self.request.POST or None
        if step == 'profile':
            return InstitutionProfileForm(data, instance=institution)
        if step == 'academic_year':
            return OnboardingAcademicYearForm(data)
        if step == 'class':
            year = institution.academic_years.order_by('-start_date').first()
            return OnboardingClassForm(data, academic_year=year)
        if step == 'fee_category':
            return OnboardingFeeCategoryForm(data)
        if step == 'fee_structure':
            return OnboardingFeeStructureForm(data, institution=institution)
        return None

    def post(self, request, *args, **kwargs):
        step = self.get_step()
        form = self.get_form(step)
        if form is None:
            return redirect(f"{reverse_lazy('accounts:onboarding')}?step=done")
        if form.is_valid():
            self.save_step(step, form)
            messages.success(request, f'{self.STEP_TITLES.get(step, step)} saved.')
            next_index = self.STEPS.index(step) + 1
            next_step = self.STEPS[min(next_index, len(self.STEPS) - 1)]
            if next_step == 'done':
                self.institution.onboarding_completed = True
                self.institution.save(update_fields=['onboarding_completed', 'updated_at'])
            return redirect(f"{reverse_lazy('accounts:onboarding')}?step={next_step}")
        return self.render_to_response(self.get_context_data(step=step, form=form))

    def save_step(self, step, form):
        if step == 'academic_year':
            academic_year = form.save(commit=False)
            academic_year.institution = self.institution
            academic_year.save()
        else:
            form.save()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = kwargs.get('step') or self.get_step()
        context['institution'] = self.institution
        context['step'] = step
        context['step_title'] = self.STEP_TITLES.get(step, step)
        context['form'] = kwargs.get('form') or self.get_form(step)
        context['steps'] = [
            {
                'key': key,
                'title': self.STEP_TITLES[key],
                'complete': self.step_complete(key),
                'active': key == step,
            }
            for key in self.STEPS
        ]
        context['progress'] = self.step_progress()
        return context

    def step_complete(self, key):
        institution = self.institution
        if key == 'profile':
            return bool(institution.address or institution.phone_number or institution.province)
        if key == 'academic_year':
            return institution.academic_years.exists()
        if key == 'class':
            return Class.objects.filter(academic_year__institution=institution).exists()
        if key == 'fee_category':
            return FeeCategory.objects.exists()
        if key == 'fee_structure':
            return FeeStructure.objects.filter(academic_year__institution=institution).exists()
        return False

    def step_progress(self):
        trackable = [key for key in self.STEPS if key != 'done']
        completed = sum(1 for key in trackable if self.step_complete(key))
        total = len(trackable)
        return {
            'completed': completed,
            'total': total,
            'percent': int(round((completed / total) * 100)) if total else 0,
        }


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


def public_search(request):
    from library.models import Book
    q = (request.GET.get('q') or '').strip().lower()
    books = []
    pages = []
    if q:
        books = (
            Book.objects
            .filter(is_active=True)
            .filter(
                Q(title__icontains=q)
                | Q(author__icontains=q)
                | Q(publisher__icontains=q)
                | Q(description__icontains=q)
                | Q(category__name__icontains=q)
            )
            .select_related('category')
            .order_by('title')[:20]
        )
        # Static index over the public marketing pages so common queries
        # return useful results even when the database has no book records.
        index = [
            (
                'AI & ChatGPT courses', 'public_courses', '#ai',
                'School of AI & Digital Skills: artificial intelligence, ChatGPT and digital skills short courses.',
                'ai artificial intelligence chatgpt digital skills machine learning prompt',
            ),
            (
                'Finance & Forex courses', 'public_courses', '#finance',
                'School of Finance, Investment & Business: forex trading, financial literacy and investment programmes.',
                'forex trading finance investment business stock market money',
            ),
            (
                'Accounting & Taxation courses', 'public_courses', '#accounting',
                'Accounting, taxation and business administration programmes for professionals and entrepreneurs.',
                'accounting taxation bookkeeping business administration quickbooks audit',
            ),
            (
                'Tuition & academic support', 'public_tuition', '',
                'New Zambian Curriculum tuition, homework assistance, revision, exam preparation and holiday classes.',
                'tuition academic support homework revision examinations tests math mathematics english science primary secondary school learner grade',
            ),
            (
                'Educational books', 'public_books', '',
                'Curriculum-aligned books for early childhood, primary and secondary, plus school stationery.',
                'books textbook curriculum ece early childhood primary secondary form1 form2 grade stationery school supplies material',
            ),
            (
                'Computers & ICT products', 'public_ict', '',
                'Desktop computers, laptops, printers and ICT accessories for learners, offices and schools.',
                'computer laptop desktop printer ict accessories hp dell canon hardware accessories',
            ),
            (
                'School solutions', 'public_school_solutions', '',
                'Computer labs, library development, bulk supply, ICT installation, teacher training and the education management dashboard.',
                'school solution laboratory lab library bulk supply procurement installation teacher training dashboard institution management',
            ),
            (
                'Shop & online orders', 'public_shop', '',
                'Order educational books, computers, laptops, printers and school supplies online.',
                'shop order buy delivery collection supplies products',
            ),
            (
                'Admissions & enrolment', 'public_admissions', '',
                'How to enrol: choose a course, confirm your intake, register and start learning.',
                'admissions enrolment enrol apply enroll register course intake fees',
            ),
        ]
        for title, url_name, anchor, description, keywords in index:
            haystack = f'{title} {description} {keywords}'.lower()
            if q in haystack:
                pages.append({'title': title, 'description': description, 'url_name': url_name, 'anchor': anchor})
    return render(request, 'public/search.html', {'query': q, 'books': books, 'pages': pages})
