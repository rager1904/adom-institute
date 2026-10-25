from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from adom.protected_media import protected_file_response
from accounts.permissions import (
    AdminRequiredMixin, IsPlatformOrInstitutionAdmin,
    is_admin_user, user_institution_ids,
)

from .models import (
    AnalyticsEvent, StudentPerformance, ClassPerformance, 
    TeacherPerformance, SchoolAnalytics, Report
)
from .serializers import (
    AnalyticsEventSerializer, StudentPerformanceSerializer, ClassPerformanceSerializer,
    TeacherPerformanceSerializer, SchoolAnalyticsSerializer, ReportSerializer
)
from .forms import ReportGenerationForm, AnalyticsFilterForm, ExportForm, DashboardFilterForm, PerformanceComparisonForm
from students.models import Student, Class, AcademicYear
from teachers.models import Teacher


def scope_to_institution(queryset, user, lookup):
    """Limit ``queryset`` to the institutions ``user`` belongs to.

    A platform administrator (``None`` from ``user_institution_ids``) sees
    everything; everybody else sees only their own institution's rows.
    """
    institution_ids = user_institution_ids(user)
    if institution_ids is None:
        return queryset
    if not institution_ids:
        return queryset.none()
    return queryset.filter(**{f'{lookup}__in': institution_ids}).distinct()


class AnalyticsAdminWriteMixin:
    """Read for signed-in users, write for institution administrators."""

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()


# API Viewsets
class AnalyticsEventViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = AnalyticsEvent.objects.all()
    serializer_class = AnalyticsEventSerializer
    permission_classes = [IsAuthenticated]


class StudentPerformanceViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = StudentPerformance.objects.all()
    serializer_class = StudentPerformanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_to_institution(
            StudentPerformance.objects.select_related('student__user', 'academic_year'),
            self.request.user, 'academic_year__institution_id',
        )


class ClassPerformanceViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = ClassPerformance.objects.all()
    serializer_class = ClassPerformanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_to_institution(
            ClassPerformance.objects.select_related('class_obj', 'academic_year'),
            self.request.user, 'academic_year__institution_id',
        )


class TeacherPerformanceViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = TeacherPerformance.objects.all()
    serializer_class = TeacherPerformanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_to_institution(
            TeacherPerformance.objects.select_related('teacher__user', 'academic_year'),
            self.request.user, 'academic_year__institution_id',
        )


class SchoolAnalyticsViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = SchoolAnalytics.objects.all()
    serializer_class = SchoolAnalyticsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_to_institution(
            SchoolAnalytics.objects.select_related('academic_year'),
            self.request.user, 'academic_year__institution_id',
        )


class ReportViewSet(AnalyticsAdminWriteMixin, viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_to_institution(
            Report.objects.select_related('generated_by'),
            self.request.user, 'generated_by__institution_memberships__institution_id',
        )


# Web Views
class DashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution_ids = user_institution_ids(self.request.user)
        context['filter_form'] = DashboardFilterForm(self.request.GET, institution_ids=institution_ids)
        context['total_students'] = StudentPerformance.objects.count()
        context['total_teachers'] = TeacherPerformance.objects.count()
        context['total_classes'] = ClassPerformance.objects.count()
        context['total_reports'] = Report.objects.count()
        return context


class MyAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/my_analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['student_performances'] = StudentPerformance.objects.none()
        context['teacher_performances'] = TeacherPerformance.objects.none()
        context['class_performances'] = ClassPerformance.objects.none()
        context['school_analytics'] = SchoolAnalytics.objects.none()

        if user.user_type == 'student':
            context['student_performances'] = StudentPerformance.objects.filter(
                student__user=user
            ).select_related('student__user', 'academic_year', 'class_obj')
        elif user.user_type == 'parent':
            context['student_performances'] = StudentPerformance.objects.filter(
                student__parents__user=user
            ).select_related('student__user', 'academic_year', 'class_obj').distinct()
        elif user.user_type == 'teacher':
            context['teacher_performances'] = TeacherPerformance.objects.filter(
                teacher__user=user
            ).select_related('teacher__user', 'academic_year')
            context['class_performances'] = ClassPerformance.objects.filter(
                class_obj__schedules__teacher__user=user
            ).select_related('class_obj', 'academic_year').distinct()
        elif is_admin_user(user):
            student_qs = StudentPerformance.objects.select_related(
                'student__user', 'academic_year', 'class_obj'
            )
            teacher_qs = TeacherPerformance.objects.select_related('teacher__user', 'academic_year')
            class_qs = ClassPerformance.objects.select_related('class_obj', 'academic_year')
            if institution_ids := user_institution_ids(user):
                student_qs = student_qs.filter(academic_year__institution_id__in=institution_ids)
                teacher_qs = teacher_qs.filter(academic_year__institution_id__in=institution_ids)
                class_qs = class_qs.filter(academic_year__institution_id__in=institution_ids)
            context['student_performances'] = student_qs[:10]
            context['teacher_performances'] = teacher_qs[:10]
            context['class_performances'] = class_qs[:10]
            context['school_analytics'] = SchoolAnalytics.objects.select_related('academic_year')[:5]

        return context


class StudentPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = StudentPerformance
    template_name = 'analytics/student_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20

    def get_queryset(self):
        queryset = StudentPerformance.objects.select_related(
            'student__user', 'academic_year', 'class_obj'
        ).order_by('-percentage')
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids:
            queryset = queryset.filter(academic_year__institution_id__in=institution_ids)
        return queryset


class ClassPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = ClassPerformance
    template_name = 'analytics/class_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20

    def get_queryset(self):
        queryset = ClassPerformance.objects.select_related(
            'class_obj', 'academic_year'
        ).order_by('-average_percentage')
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids:
            queryset = queryset.filter(academic_year__institution_id__in=institution_ids)
        return queryset


class TeacherPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = TeacherPerformance
    template_name = 'analytics/teacher_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20

    def get_queryset(self):
        queryset = TeacherPerformance.objects.select_related(
            'teacher__user', 'academic_year'
        ).order_by('-average_class_performance')
        institution_ids = user_institution_ids(self.request.user)
        if institution_ids:
            queryset = queryset.filter(academic_year__institution_id__in=institution_ids)
        return queryset


class ReportListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Report
    template_name = 'analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        return scope_to_institution(
            Report.objects.select_related('generated_by'),
            self.request.user,
            'generated_by__institution_memberships__institution_id',
        ).order_by('-generated_at')


class ReportDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Report
    template_name = 'analytics/report_detail_modern.html'
    context_object_name = 'report'

    def get_queryset(self):
        return scope_to_institution(
            Report.objects.select_related('generated_by'),
            self.request.user,
            'generated_by__institution_memberships__institution_id',
        )


class ReportCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Report
    form_class = ReportGenerationForm
    template_name = 'analytics/report_form_modern.html'
    success_url = reverse_lazy('analytics:report_list')

    def form_valid(self, form):
        form.instance.generated_by = self.request.user
        form.instance.status = Report.ReportStatus.GENERATED
        messages.success(self.request, 'Report created successfully.')
        return super().form_valid(form)


class ReportUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Report
    form_class = ReportGenerationForm
    template_name = 'analytics/report_form_modern.html'
    success_url = reverse_lazy('analytics:report_list')

    def get_queryset(self):
        return scope_to_institution(
            Report.objects.all(),
            self.request.user,
            'generated_by__institution_memberships__institution_id',
        )

    def form_valid(self, form):
        messages.success(self.request, 'Report updated successfully.')
        return super().form_valid(form)


class ReportDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Report
    template_name = 'analytics/report_confirm_delete_modern.html'
    success_url = reverse_lazy('analytics:report_list')
    context_object_name = 'report'

    def get_queryset(self):
        return scope_to_institution(
            Report.objects.all(),
            self.request.user,
            'generated_by__institution_memberships__institution_id',
        )


@login_required
def report_file(request, pk):
    """Stream a generated report through the authenticated inline viewer.

    Generated reports can contain sensitive institutional data, so the raw
    ``/media/reports/`` URL must never be handed to a client.
    """
    if not is_admin_user(request.user):
        raise PermissionDenied

    report = get_object_or_404(Report, pk=pk)
    if not report.file_path:
        raise Http404('This report has no generated file.')

    institution_ids = user_institution_ids(request.user)
    if institution_ids is not None:
        belongs = (
            report.generated_by_id is not None
            and report.generated_by.institution_memberships.filter(
                institution_id__in=institution_ids
            ).exists()
        )
        if not belongs:
            raise PermissionDenied

    return protected_file_response(
        report.file_path, request=request, filename=report.name,
    )
