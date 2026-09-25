from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, TemplateView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.contrib import messages
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import AdminRequiredMixin, is_admin_user

from .models import (
    AnalyticsEvent, StudentPerformance, ClassPerformance, 
    TeacherPerformance, SchoolAnalytics, Report
)
from .serializers import (
    AnalyticsEventSerializer, StudentPerformanceSerializer, ClassPerformanceSerializer,
    TeacherPerformanceSerializer, SchoolAnalyticsSerializer, ReportSerializer
)
from .forms import ReportGenerationForm


# API Viewsets
class AnalyticsEventViewSet(viewsets.ModelViewSet):
    queryset = AnalyticsEvent.objects.all()
    serializer_class = AnalyticsEventSerializer
    permission_classes = [IsAuthenticated]


class StudentPerformanceViewSet(viewsets.ModelViewSet):
    queryset = StudentPerformance.objects.all()
    serializer_class = StudentPerformanceSerializer
    permission_classes = [IsAuthenticated]


class ClassPerformanceViewSet(viewsets.ModelViewSet):
    queryset = ClassPerformance.objects.all()
    serializer_class = ClassPerformanceSerializer
    permission_classes = [IsAuthenticated]


class TeacherPerformanceViewSet(viewsets.ModelViewSet):
    queryset = TeacherPerformance.objects.all()
    serializer_class = TeacherPerformanceSerializer
    permission_classes = [IsAuthenticated]


class SchoolAnalyticsViewSet(viewsets.ModelViewSet):
    queryset = SchoolAnalytics.objects.all()
    serializer_class = SchoolAnalyticsSerializer
    permission_classes = [IsAuthenticated]


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]


# Web Views
class DashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
            context['student_performances'] = StudentPerformance.objects.select_related(
                'student__user', 'academic_year', 'class_obj'
            )[:10]
            context['teacher_performances'] = TeacherPerformance.objects.select_related(
                'teacher__user', 'academic_year'
            )[:10]
            context['class_performances'] = ClassPerformance.objects.select_related(
                'class_obj', 'academic_year'
            )[:10]
            context['school_analytics'] = SchoolAnalytics.objects.select_related('academic_year')[:5]

        return context


class StudentPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = StudentPerformance
    template_name = 'analytics/student_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20


class ClassPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = ClassPerformance
    template_name = 'analytics/class_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20


class TeacherPerformanceListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = TeacherPerformance
    template_name = 'analytics/teacher_performance_list.html'
    context_object_name = 'performances'
    paginate_by = 20


class ReportListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Report
    template_name = 'analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20


class ReportDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Report
    template_name = 'analytics/report_detail_modern.html'
    context_object_name = 'report'


class ReportCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Report
    form_class = ReportGenerationForm
    template_name = 'analytics/report_form_modern.html'
    success_url = reverse_lazy('analytics:report_list')

    def form_valid(self, form):
        form.instance.generated_by = self.request.user
        messages.success(self.request, 'Report created successfully.')
        return super().form_valid(form)


class ReportUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Report
    form_class = ReportGenerationForm
    template_name = 'analytics/report_form_modern.html'
    success_url = reverse_lazy('analytics:report_list')

    def form_valid(self, form):
        messages.success(self.request, 'Report updated successfully.')
        return super().form_valid(form)


class ReportDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Report
    template_name = 'analytics/report_confirm_delete_modern.html'
    success_url = reverse_lazy('analytics:report_list')
    context_object_name = 'report'
