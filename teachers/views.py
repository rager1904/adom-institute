from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, FormView
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import AdminRequiredMixin, is_platform_admin, user_institution_ids
from .models import Teacher, Subject, TeacherSubject, Department, TeacherDepartment
from .forms import (
    TeacherForm, SubjectForm, DepartmentForm, TeacherSubjectForm, TeacherDepartmentForm,
    TeacherSearchForm, SubjectSearchForm, DepartmentSearchForm, TeacherClassSubjectAssignmentForm
)


# API Viewsets
class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.select_related('user').prefetch_related('teacher_subjects__subject', 'teacher_departments__department')
    serializer_class = None  # Will be defined in serializers.py
    
    def get_queryset(self):
        queryset = Teacher.objects.select_related('user').prefetch_related('teacher_subjects__subject', 'teacher_departments__department')
        user = self.request.user
        if is_platform_admin(user):
            pass
        elif user.user_type == 'teacher':
            queryset = queryset.filter(user=user)
        elif user.user_type == 'student':
            queryset = queryset.filter(schedules__class_obj__students__user=user)
        elif user.user_type == 'parent':
            queryset = queryset.filter(schedules__class_obj__students__parents__user=user)
        else:
            institution_ids = user_institution_ids(user)
            queryset = queryset.filter(user__institution_memberships__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        # Filtering
        employment_type = self.request.query_params.get('employment_type', None)
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
        
        employment_status = self.request.query_params.get('employment_status', None)
        if employment_status:
            queryset = queryset.filter(employment_status=employment_status)
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(qualification__icontains=search)
            )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        total_teachers = Teacher.objects.count()
        active_teachers = Teacher.objects.filter(employment_status=Teacher.EmploymentStatus.ACTIVE).count()
        full_time_teachers = Teacher.objects.filter(employment_type=Teacher.EmploymentType.FULL_TIME).count()
        class_teachers = Teacher.objects.filter(is_class_teacher=True).count()
        
        return Response({
            'total_teachers': total_teachers,
            'active_teachers': active_teachers,
            'full_time_teachers': full_time_teachers,
            'class_teachers': class_teachers,
        })


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.prefetch_related('teacher_subjects__teacher__user')
    serializer_class = None  # Will be defined in serializers.py
    
    def get_queryset(self):
        queryset = Subject.objects.prefetch_related('teacher_subjects__teacher__user')
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('head_of_department__user').prefetch_related('teacher_departments__teacher__user')
    serializer_class = None  # Will be defined in serializers.py
    
    def get_queryset(self):
        queryset = Department.objects.select_related('head_of_department__user').prefetch_related('teacher_departments__teacher__user')
        
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset


# Web Views
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'teachers/dashboard.html'

    def get_teacher_queryset(self):
        queryset = Teacher.objects.select_related('user')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(user=user)
        if user.user_type == 'student':
            return queryset.filter(schedules__class_obj__students__user=user).distinct()
        if user.user_type == 'parent':
            return queryset.filter(schedules__class_obj__students__parents__user=user).distinct()
        institution_ids = user_institution_ids(user)
        if institution_ids:
            return queryset.filter(user__institution_memberships__institution_id__in=institution_ids).distinct()
        return queryset.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        teachers = self.get_teacher_queryset()
        context['total_teachers'] = teachers.count()
        context['active_teachers'] = teachers.filter(employment_status=Teacher.EmploymentStatus.ACTIVE).count()
        context['full_time_teachers'] = teachers.filter(employment_type=Teacher.EmploymentType.FULL_TIME).count()
        context['part_time_teachers'] = teachers.filter(employment_type=Teacher.EmploymentType.PART_TIME).count()
        context['class_teachers'] = teachers.filter(is_class_teacher=True).count()
        context['head_of_departments'] = teachers.filter(is_head_of_department=True).count()
        
        # Subject statistics
        context['total_subjects'] = Subject.objects.filter(teacher_subjects__teacher__in=teachers).distinct().count()
        context['active_subjects'] = Subject.objects.filter(teacher_subjects__teacher__in=teachers, is_active=True).distinct().count()
        
        # Department statistics
        context['total_departments'] = Department.objects.filter(teacher_departments__teacher__in=teachers).distinct().count()
        context['active_departments'] = Department.objects.filter(teacher_departments__teacher__in=teachers, is_active=True).distinct().count()
        context['departments_with_heads'] = Department.objects.filter(teacher_departments__teacher__in=teachers, head_of_department__isnull=False).distinct().count()
        
        # Recent teachers
        context['recent_teachers'] = teachers.order_by('-created_at')[:5]
        
        # Employment type distribution
        employment_types = teachers.values('employment_type').annotate(count=Count('id'))
        context['employment_type_data'] = {
            item['employment_type']: item['count'] for item in employment_types
        }
        
        # Employment status distribution
        employment_statuses = teachers.values('employment_status').annotate(count=Count('id'))
        context['employment_status_data'] = {
            item['employment_status']: item['count'] for item in employment_statuses
        }
        
        return context


class MyTeachingView(LoginRequiredMixin, TemplateView):
    template_name = 'teachers/my_teaching.html'

    def get_teacher(self):
        return getattr(self.request.user, 'teacher_profile', None)

    def get_context_data(self, **kwargs):
        from academics.models import Assignment, StudentAssignment
        from attendance.models import ClassAttendance
        from students.models import Student
        from timetable.models import ClassSchedule

        context = super().get_context_data(**kwargs)
        teacher = self.get_teacher()
        if teacher is None:
            context.update({
                'teacher': None,
                'classes': [],
                'today_schedules': [],
                'recent_assignments': [],
                'ungraded_submissions': [],
                'pending_attendance_classes': [],
                'student_count': 0,
            })
            return context

        today = timezone.localdate()
        today_day = today.strftime('%A').lower()
        schedules = ClassSchedule.objects.filter(
            teacher=teacher,
            is_active=True,
        ).select_related('class_obj', 'subject', 'room', 'time_slot')
        classes = list({schedule.class_obj for schedule in schedules})
        class_ids = [class_obj.pk for class_obj in classes]
        marked_class_ids = set(
            ClassAttendance.objects.filter(
                class_obj_id__in=class_ids,
                date=today,
            ).values_list('class_obj_id', flat=True)
        )
        assignments = Assignment.objects.filter(teacher=teacher).select_related('subject', 'class_obj')
        ungraded = StudentAssignment.objects.filter(
            assignment__teacher=teacher,
            marks_obtained__isnull=True,
        ).select_related('student__user', 'assignment__subject', 'assignment__class_obj')

        context.update({
            'teacher': teacher,
            'classes': classes,
            'today_schedules': schedules.filter(time_slot__day=today_day).order_by('time_slot__start_time'),
            'recent_assignments': assignments.order_by('-created_at')[:8],
            'ungraded_submissions': ungraded.order_by('-submitted_at')[:8],
            'pending_attendance_classes': [class_obj for class_obj in classes if class_obj.pk not in marked_class_ids],
            'student_count': Student.objects.filter(current_class_id__in=class_ids, is_active=True).count(),
        })
        return context


class TeacherClassSubjectAssignmentView(LoginRequiredMixin, AdminRequiredMixin, FormView):
    template_name = 'teachers/class_subject_assignment.html'
    form_class = TeacherClassSubjectAssignmentForm
    success_url = reverse_lazy('teachers:class_subject_assignment')

    def get_institution_ids(self):
        if is_platform_admin(self.request.user):
            return None
        return user_institution_ids(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['institution_ids'] = self.get_institution_ids()
        return kwargs

    def get_context_data(self, **kwargs):
        from timetable.models import ClassSchedule

        context = super().get_context_data(**kwargs)
        institution_ids = self.get_institution_ids()
        assignments = ClassSchedule.objects.select_related(
            'class_obj__academic_year__institution', 'subject', 'teacher__user', 'room', 'time_slot'
        ).filter(is_active=True)
        if institution_ids is not None:
            assignments = assignments.filter(class_obj__academic_year__institution_id__in=institution_ids)
        context['assignments'] = assignments.order_by('time_slot__day', 'time_slot__start_time')[:20]
        return context

    def form_valid(self, form):
        schedule = form.save()
        messages.success(
            self.request,
            f'{schedule.teacher.user.get_full_name()} assigned to {schedule.subject.name} for {schedule.class_obj.display_name}.'
        )
        return super().form_valid(form)


# Teacher Views
class TeacherListView(LoginRequiredMixin, ListView):
    model = Teacher
    template_name = 'teachers/teacher_list.html'
    context_object_name = 'teachers'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Teacher.objects.select_related('user').prefetch_related('teacher_subjects__subject', 'teacher_departments__department')
        
        # Apply search and filters
        search_form = TeacherSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(employee_id__icontains=search) |
                    Q(qualification__icontains=search)
                )
            
            employment_type = search_form.cleaned_data.get('employment_type_filter')
            if employment_type:
                queryset = queryset.filter(employment_type=employment_type)
            
            employment_status = search_form.cleaned_data.get('employment_status_filter')
            if employment_status:
                queryset = queryset.filter(employment_status=employment_status)
        
        return queryset.distinct().order_by('user__first_name', 'user__last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = TeacherSearchForm(self.request.GET)
        return context


class TeacherDetailView(LoginRequiredMixin, DetailView):
    model = Teacher
    template_name = 'teachers/teacher_detail.html'
    context_object_name = 'teacher'
    
    def get_queryset(self):
        queryset = Teacher.objects.select_related('user').prefetch_related(
            'teacher_subjects__subject', 
            'teacher_departments__department'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(user=user)
        if user.user_type == 'student':
            return queryset.filter(schedules__class_obj__students__user=user).distinct()
        if user.user_type == 'parent':
            return queryset.filter(schedules__class_obj__students__parents__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(user__institution_memberships__institution_id__in=institution_ids).distinct() if institution_ids else queryset.none()


class TeacherCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'teachers/teacher_form_modern.html'
    success_url = reverse_lazy('teachers:teacher_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Teacher created successfully!')
        return super().form_valid(form)


class TeacherUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'teachers/teacher_form_modern.html'
    success_url = reverse_lazy('teachers:teacher_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Teacher updated successfully!')
        return super().form_valid(form)


class TeacherDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'teachers/teacher_confirm_delete.html'
    success_url = reverse_lazy('teachers:teacher_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Teacher deleted successfully!')
        return super().delete(request, *args, **kwargs)


# Subject Views
class SubjectListView(LoginRequiredMixin, ListView):
    model = Subject
    template_name = 'teachers/subject_list.html'
    context_object_name = 'subjects'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Subject.objects.prefetch_related('teacher_subjects__teacher__user')
        user = self.request.user
        if is_platform_admin(user):
            pass
        elif user.user_type == 'teacher':
            queryset = queryset.filter(Q(teacher_subjects__teacher__user=user) | Q(schedules__teacher__user=user))
        elif user.user_type == 'student':
            queryset = queryset.filter(schedules__class_obj__students__user=user)
        elif user.user_type == 'parent':
            queryset = queryset.filter(schedules__class_obj__students__parents__user=user)
        else:
            institution_ids = user_institution_ids(user)
            queryset = queryset.filter(schedules__class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        search_form = SubjectSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(code__icontains=search) |
                    Q(description__icontains=search)
                )
            
            is_active = search_form.cleaned_data.get('is_active_filter')
            if is_active:
                queryset = queryset.filter(is_active=is_active == 'True')
        
        return queryset.distinct().order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = SubjectSearchForm(self.request.GET)
        return context


class SubjectDetailView(LoginRequiredMixin, DetailView):
    model = Subject
    template_name = 'teachers/subject_detail.html'
    context_object_name = 'subject'
    
    def get_queryset(self):
        queryset = Subject.objects.prefetch_related('teacher_subjects__teacher__user')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher_subjects__teacher__user=user) | Q(schedules__teacher__user=user)).distinct()
        if user.user_type == 'student':
            return queryset.filter(schedules__class_obj__students__user=user).distinct()
        if user.user_type == 'parent':
            return queryset.filter(schedules__class_obj__students__parents__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(schedules__class_obj__academic_year__institution_id__in=institution_ids).distinct() if institution_ids else queryset.none()


class SubjectCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'teachers/subject_form.html'
    success_url = reverse_lazy('teachers:subject_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Subject created successfully!')
        return super().form_valid(form)


class SubjectUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'teachers/subject_form.html'
    success_url = reverse_lazy('teachers:subject_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Subject updated successfully!')
        return super().form_valid(form)


class SubjectDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Subject
    template_name = 'teachers/subject_confirm_delete.html'
    success_url = reverse_lazy('teachers:subject_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Subject deleted successfully!')
        return super().delete(request, *args, **kwargs)


# Department Views
class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = 'teachers/department_list.html'
    context_object_name = 'departments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Department.objects.select_related('head_of_department__user').prefetch_related('teacher_departments__teacher__user')
        user = self.request.user
        if is_platform_admin(user):
            pass
        elif user.user_type == 'teacher':
            queryset = queryset.filter(teacher_departments__teacher__user=user)
        else:
            institution_ids = user_institution_ids(user)
            queryset = queryset.filter(teacher_departments__teacher__user__institution_memberships__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        search_form = DepartmentSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(code__icontains=search) |
                    Q(description__icontains=search)
                )
            
            is_active = search_form.cleaned_data.get('is_active_filter')
            if is_active:
                queryset = queryset.filter(is_active=is_active == 'True')
        
        return queryset.distinct().order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DepartmentSearchForm(self.request.GET)
        return context


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = 'teachers/department_detail.html'
    context_object_name = 'department'
    
    def get_queryset(self):
        queryset = Department.objects.select_related('head_of_department__user').prefetch_related('teacher_departments__teacher__user')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(teacher_departments__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(teacher_departments__teacher__user__institution_memberships__institution_id__in=institution_ids).distinct() if institution_ids else queryset.none()


class DepartmentCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'teachers/department_form.html'
    success_url = reverse_lazy('teachers:department_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Department created successfully!')
        return super().form_valid(form)


class DepartmentUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'teachers/department_form.html'
    success_url = reverse_lazy('teachers:department_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Department updated successfully!')
        return super().form_valid(form)


class DepartmentDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Department
    template_name = 'teachers/department_confirm_delete.html'
    success_url = reverse_lazy('teachers:department_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Department deleted successfully!')
        return super().delete(request, *args, **kwargs)
