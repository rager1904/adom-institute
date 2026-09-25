from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.views.generic.base import TemplateView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Avg, Sum, ExpressionWrapper, F, FloatField, Value
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from datetime import datetime, timedelta

from accounts.permissions import (
    InstitutionScopedQuerysetMixin, IsPlatformOrInstitutionAdmin,
    InstitutionAccessMixin, StudentAccessMixin, UserScopedQuerysetMixin,
    AdminRequiredMixin, is_platform_admin, user_can_access_institution, user_institution_ids
)
from .models import AcademicYear, Class, Student, Parent
from .forms import (
    AcademicYearForm, ClassForm, StudentForm, ParentForm,
    StudentSearchForm, ClassSearchForm, ParentSearchForm, StudentClassPlacementForm
)
from .serializers import (
    AcademicYearSerializer, AcademicYear_CreateSerializer, AcademicYearDetailSerializer, AcademicYearSummarySerializer,
    ClassSerializer, Class_CreateSerializer, ClassDetailSerializer, ClassSummarySerializer,
    StudentSerializer, Student_CreateSerializer, StudentDetailSerializer, StudentSummarySerializer, StudentReportSerializer,
    ParentSerializer, Parent_CreateSerializer,
    DashboardStatsSerializer
)


def scope_students_for_request(request, queryset):
    return StudentAccessMixin.scope_student_queryset(type('Scoped', (), {'request': request})(), queryset)


def scope_institution_for_request(request, queryset, lookup):
    return InstitutionAccessMixin.scope_institution_queryset(type('Scoped', (), {'request': request})(), queryset, lookup)


# API Viewsets
class AcademicYearViewSet(InstitutionScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all().order_by('-start_date')
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAuthenticated]
    institution_lookup = 'institution_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'start_date', 'end_date', 'is_active']
    ordering = ['-start_date']

    def get_serializer_class(self):
        if self.action == 'create':
            return AcademicYear_CreateSerializer
        elif self.action == 'retrieve':
            return AcademicYearDetailSerializer
        elif self.action in ['list']:
            return AcademicYearSummarySerializer
        return AcademicYearSerializer

    def get_queryset(self):
        queryset = AcademicYear.objects.select_related('institution').order_by('-start_date')
        return self.filter_by_institution(queryset)

    def perform_create(self, serializer):
        institution = serializer.validated_data.get('institution')
        if not user_can_access_institution(self.request.user, getattr(institution, 'id', None)):
            raise PermissionDenied('You cannot create academic years for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        institution = serializer.validated_data.get('institution', serializer.instance.institution)
        if not user_can_access_institution(self.request.user, getattr(institution, 'id', None)):
            raise PermissionDenied('You cannot move academic years to this institution.')
        serializer.save()

    @action(detail=True, methods=['get'])
    def classes(self, request, pk=None):
        academic_year = self.get_object()
        classes = academic_year.classes.all()
        serializer = ClassSummarySerializer(classes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if active_year:
            serializer = AcademicYearSerializer(active_year)
            return Response(serializer.data)
        return Response({'detail': 'No active academic year found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        academic_year = self.get_object()
        # Deactivate all other academic years
        AcademicYear.objects.update(is_active=False)
        # Activate this academic year
        academic_year.is_active = True
        academic_year.save()
        serializer = AcademicYearSerializer(academic_year)
        return Response(serializer.data)


class ClassViewSet(InstitutionScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Class.objects.all().order_by('academic_year', 'name')
    serializer_class = ClassSerializer
    permission_classes = [IsAuthenticated]
    institution_lookup = 'academic_year__institution_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'display_name', 'section']
    ordering_fields = ['name', 'display_name', 'capacity', 'is_active']
    ordering = ['academic_year', 'name']

    def get_serializer_class(self):
        if self.action == 'create':
            return Class_CreateSerializer
        elif self.action == 'retrieve':
            return ClassDetailSerializer
        elif self.action in ['list']:
            return ClassSummarySerializer
        return ClassSerializer

    def get_queryset(self):
        queryset = self.filter_by_institution(
            Class.objects.select_related('academic_year', 'academic_year__institution').order_by('academic_year', 'name')
        )
        academic_year = self.request.query_params.get('academic_year', None)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset

    def perform_create(self, serializer):
        academic_year = serializer.validated_data.get('academic_year')
        if not user_can_access_institution(self.request.user, getattr(academic_year, 'institution_id', None)):
            raise PermissionDenied('You cannot create classes for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        academic_year = serializer.validated_data.get('academic_year', serializer.instance.academic_year)
        if not user_can_access_institution(self.request.user, getattr(academic_year, 'institution_id', None)):
            raise PermissionDenied('You cannot move classes to this institution.')
        serializer.save()

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        class_obj = self.get_object()
        students = class_obj.students.all()
        serializer = StudentSummarySerializer(students, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        class_obj = self.get_object()
        class_obj.is_active = True
        class_obj.save()
        serializer = ClassSerializer(class_obj)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        class_obj = self.get_object()
        class_obj.is_active = False
        class_obj.save()
        serializer = ClassSerializer(class_obj)
        return Response(serializer.data)


class StudentViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by('-created_at')
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['student_id', 'admission_number', 'roll_number', 'user__first_name', 'user__last_name', 'user__email']
    ordering_fields = ['student_id', 'admission_date', 'created_at', 'is_active']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'approve_admission', 'reject_admission']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        current_class = serializer.validated_data.get('current_class')
        institution_id = getattr(getattr(current_class, 'academic_year', None), 'institution_id', None)
        if not user_can_access_institution(self.request.user, institution_id):
            raise PermissionDenied('You cannot create students for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        current_class = serializer.validated_data.get('current_class', serializer.instance.current_class)
        institution_id = getattr(getattr(current_class, 'academic_year', None), 'institution_id', None)
        if not user_can_access_institution(self.request.user, institution_id):
            raise PermissionDenied('You cannot move students to this institution.')
        serializer.save()

    def get_serializer_class(self):
        if self.action == 'create':
            return Student_CreateSerializer
        elif self.action == 'retrieve':
            return StudentDetailSerializer
        elif self.action in ['list']:
            return StudentSummarySerializer
        elif self.action == 'report':
            return StudentReportSerializer
        return StudentSerializer

    def get_queryset(self):
        queryset = self.scoped_students(
            Student.objects.select_related(
                'user', 'current_class', 'current_class__academic_year', 'current_class__academic_year__institution'
            ).prefetch_related('parents__user').order_by('-created_at')
        )
        class_filter = self.request.query_params.get('class', None)
        status_filter = self.request.query_params.get('status', None)
        gender_filter = self.request.query_params.get('gender', None)
        
        if class_filter:
            queryset = queryset.filter(current_class_id=class_filter)
        if status_filter:
            queryset = queryset.filter(admission_status=status_filter)
        if gender_filter:
            queryset = queryset.filter(gender=gender_filter)
        
        return queryset

    @action(detail=True, methods=['get'])
    def parents(self, request, pk=None):
        student = self.get_object()
        parents = student.parents.all()
        serializer = ParentSerializer(parents, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve_admission(self, request, pk=None):
        student = self.get_object()
        student.admission_status = 'approved'
        student.save()
        serializer = StudentSerializer(student)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject_admission(self, request, pk=None):
        student = self.get_object()
        student.admission_status = 'rejected'
        student.save()
        serializer = StudentSerializer(student)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def report(self, request):
        students = self.get_queryset()
        serializer = StudentReportSerializer(students, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        total_students = Student.objects.count()
        active_students = Student.objects.filter(is_active=True).count()
        pending_admissions = Student.objects.filter(admission_status='pending').count()
        
        students_by_gender = Student.objects.values('gender').annotate(count=Count('id'))
        students_by_status = Student.objects.values('admission_status').annotate(count=Count('id'))
        
        recent_admissions = Student.objects.order_by('-created_at')[:10]
        
        data = {
            'total_students': total_students,
            'active_students': active_students,
            'pending_admissions': pending_admissions,
            'students_by_gender': {item['gender']: item['count'] for item in students_by_gender},
            'students_by_status': {item['admission_status']: item['count'] for item in students_by_status},
            'recent_admissions': StudentSummarySerializer(recent_admissions, many=True).data
        }
        
        return Response(data)


class ParentViewSet(viewsets.ModelViewSet):
    queryset = Parent.objects.all().order_by('-created_at')
    serializer_class = ParentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'phone_number', 'student__student_id']
    ordering_fields = ['relationship', 'created_at']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'set_primary_contact', 'set_emergency_contact']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        if not user_can_access_institution(self.request.user, institution_id):
            raise PermissionDenied('You cannot create parent records for this institution.')
        serializer.save()

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        if not user_can_access_institution(self.request.user, institution_id):
            raise PermissionDenied('You cannot move parent records to this institution.')
        serializer.save()

    def get_serializer_class(self):
        if self.action == 'create':
            return Parent_CreateSerializer
        return ParentSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Parent.objects.select_related(
            'user', 'student__user', 'student__current_class__academic_year__institution'
        ).order_by('-created_at')

        if not is_platform_admin(user):
            institution_ids = user_institution_ids(user)
            if getattr(user, 'user_type', None) == 'parent':
                queryset = queryset.filter(user=user)
            elif getattr(user, 'user_type', None) == 'student':
                queryset = queryset.filter(student__user=user)
            elif institution_ids:
                queryset = queryset.filter(
                    student__current_class__academic_year__institution_id__in=institution_ids
                )
            else:
                queryset = queryset.none()

        student_filter = self.request.query_params.get('student', None)
        relationship_filter = self.request.query_params.get('relationship', None)
        
        if student_filter:
            queryset = queryset.filter(student_id=student_filter)
        if relationship_filter:
            queryset = queryset.filter(relationship=relationship_filter)
        
        return queryset

    @action(detail=True, methods=['post'])
    def set_primary_contact(self, request, pk=None):
        parent = self.get_object()
        # Remove primary contact from other parents of the same student
        Parent.objects.filter(student=parent.student, is_primary_contact=True).update(is_primary_contact=False)
        # Set this parent as primary contact
        parent.is_primary_contact = True
        parent.save()
        serializer = ParentSerializer(parent)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_emergency_contact(self, request, pk=None):
        parent = self.get_object()
        # Remove emergency contact from other parents of the same student
        Parent.objects.filter(student=parent.student, is_emergency_contact=True).update(is_emergency_contact=False)
        # Set this parent as emergency contact
        parent.is_emergency_contact = True
        parent.save()
        serializer = ParentSerializer(parent)
        return Response(serializer.data)


# Web-based Views
class StudentPortalView(LoginRequiredMixin, StudentAccessMixin, TemplateView):
    template_name = 'students/student_portal.html'

    def get_students(self):
        queryset = Student.objects.select_related(
            'user',
            'current_class',
            'current_class__academic_year',
            'current_class__academic_year__institution',
        ).prefetch_related('parents__user')
        return self.scope_student_queryset(queryset).distinct().order_by('user__first_name', 'user__last_name')

    def get_context_data(self, **kwargs):
        from academics.models import Assignment, ExamSubject, StudentAssignment
        from analytics.models import StudentPerformance
        from attendance.models import Attendance
        from communication.models import Message
        from adom_institute.models import AgentTask
        from fees.models import StudentFee

        context = super().get_context_data(**kwargs)
        students = list(self.get_students())
        student_ids = [student.pk for student in students]
        current_class_ids = [student.current_class_id for student in students if student.current_class_id]
        now = timezone.now()
        today = timezone.localdate()

        attendance_qs = Attendance.objects.filter(student_id__in=student_ids)
        total_attendance = attendance_qs.count()
        present_attendance = attendance_qs.filter(
            status__in=[
                Attendance.AttendanceStatus.PRESENT,
                Attendance.AttendanceStatus.LATE,
                Attendance.AttendanceStatus.HALF_DAY,
            ]
        ).count()
        attendance_rate = round((present_attendance / total_attendance) * 100, 1) if total_attendance else None

        fee_totals = StudentFee.objects.filter(student_id__in=student_ids).exclude(
            payment_status=StudentFee.PaymentStatus.PAID
        ).aggregate(amount=Sum('amount'), paid=Sum('paid_amount'))
        outstanding_fee_total = (fee_totals['amount'] or 0) - (fee_totals['paid'] or 0)

        assignments = Assignment.objects.filter(
            class_obj_id__in=current_class_ids,
            due_date__gte=now,
        ).select_related('subject', 'class_obj').order_by('due_date')[:8]
        submitted_assignment_ids = set(
            StudentAssignment.objects.filter(
                student_id__in=student_ids,
                assignment__in=assignments,
            ).values_list('assignment_id', flat=True)
        )

        upcoming_exams = ExamSubject.objects.filter(
            exam__class_obj_id__in=current_class_ids,
            exam_date__gte=today,
        ).select_related('exam', 'subject', 'exam__class_obj').order_by('exam_date')[:8]

        performances = StudentPerformance.objects.filter(
            student_id__in=student_ids,
        ).select_related('student__user', 'academic_year', 'class_obj').order_by(
            '-academic_year__start_date', '-percentage'
        )

        messages_qs = Message.objects.filter(recipients=self.request.user).select_related('sender').order_by('-sent_at')
        ai_recommendations = AgentTask.objects.filter(created_by=self.request.user).order_by('-created_at')[:5]

        context.update({
            'portal_students': students,
            'attendance_rate': attendance_rate,
            'attendance_total': total_attendance,
            'outstanding_fee_total': outstanding_fee_total,
            'upcoming_assignments': assignments,
            'submitted_assignment_ids': submitted_assignment_ids,
            'upcoming_exams': upcoming_exams,
            'performances': performances[:5],
            'recent_messages': messages_qs[:5],
            'ai_recommendations': ai_recommendations,
        })
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'students/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scoped_students = Student.objects.select_related('current_class__academic_year__institution')
        scoped_students = StudentAccessMixin.scope_student_queryset(self, scoped_students)
        scoped_classes = Class.objects.select_related('academic_year__institution')
        scoped_classes = InstitutionAccessMixin.scope_institution_queryset(
            self, scoped_classes, 'academic_year__institution_id'
        )
        scoped_parents = Parent.objects.select_related('student__current_class__academic_year__institution')
        user = self.request.user
        if not is_platform_admin(user):
            institution_ids = user_institution_ids(user)
            if user.user_type == 'parent':
                scoped_parents = scoped_parents.filter(user=user)
            elif user.user_type == 'student':
                scoped_parents = scoped_parents.filter(student__user=user)
            elif institution_ids:
                scoped_parents = scoped_parents.filter(student__current_class__academic_year__institution_id__in=institution_ids)
            else:
                scoped_parents = scoped_parents.none()
        
        # Basic statistics
        context['total_students'] = scoped_students.count()
        context['active_students'] = scoped_students.filter(is_active=True).count()
        context['pending_admissions'] = scoped_students.filter(admission_status='pending').count()
        context['total_classes'] = scoped_classes.filter(is_active=True).count()
        context['total_parents'] = scoped_parents.count()
        
        # Gender distribution
        context['students_by_gender'] = scoped_students.values('gender').annotate(count=Count('id'))
        
        # Status distribution
        context['students_by_status'] = scoped_students.values('admission_status').annotate(count=Count('id'))
        
        # Recent admissions
        context['recent_admissions'] = scoped_students.order_by('-created_at')[:5]
        
        # Class capacity utilization
        context['class_utilization'] = scoped_classes.filter(is_active=True).annotate(
            student_count=Count('students'),
            utilization=ExpressionWrapper(
                Count('students') * Value(100.0) / F('capacity'),
                output_field=FloatField(),
            )
        )[:10]
        
        return context


class StudentListView(LoginRequiredMixin, StudentAccessMixin, ListView):
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = self.scope_student_queryset(
            Student.objects.select_related(
                'user', 'current_class__academic_year__institution'
            ).prefetch_related('parents')
        )
        
        # Apply search filters
        search = self.request.GET.get('search')
        class_filter = self.request.GET.get('class_filter')
        status_filter = self.request.GET.get('status_filter')
        gender_filter = self.request.GET.get('gender_filter')
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(student_id__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        if class_filter:
            queryset = queryset.filter(current_class_id=class_filter)
        
        if status_filter:
            queryset = queryset.filter(admission_status=status_filter)
        
        if gender_filter:
            queryset = queryset.filter(gender=gender_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = StudentSearchForm(self.request.GET)
        return context


class StudentDetailView(LoginRequiredMixin, StudentAccessMixin, DetailView):
    model = Student
    template_name = 'students/student_detail_modern.html'
    context_object_name = 'student'
    
    def get_queryset(self):
        return self.scope_student_queryset(
            Student.objects.select_related(
                'user', 'current_class__academic_year__institution'
            ).prefetch_related('parents__user')
        )


class StudentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'
    permission_required = 'students.add_student'
    success_url = reverse_lazy('students:student_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Student created successfully!')
        return super().form_valid(form)


class StudentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'
    permission_required = 'students.change_student'
    
    def get_success_url(self):
        return reverse('students:student_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Student updated successfully!')
        return super().form_valid(form)


class StudentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Student
    template_name = 'students/student_confirm_delete.html'
    permission_required = 'students.delete_student'
    success_url = reverse_lazy('students:student_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Student deleted successfully!')
        return super().delete(request, *args, **kwargs)


class ClassListView(LoginRequiredMixin, InstitutionAccessMixin, ListView):
    model = Class
    template_name = 'students/class_list.html'
    context_object_name = 'classes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Class.objects.select_related('academic_year__institution').prefetch_related('students')
        user = self.request.user
        if is_platform_admin(user):
            pass
        elif user.user_type == 'student':
            queryset = queryset.filter(students__user=user)
        elif user.user_type == 'parent':
            queryset = queryset.filter(students__parents__user=user)
        elif user.user_type == 'teacher':
            queryset = queryset.filter(schedules__teacher__user=user)
        else:
            queryset = self.scope_institution_queryset(queryset, 'academic_year__institution_id')
        
        # Apply search filters
        search = self.request.GET.get('search')
        academic_year_filter = self.request.GET.get('academic_year_filter')
        section_filter = self.request.GET.get('section_filter')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(display_name__icontains=search) |
                Q(section__icontains=search)
            )
        
        if academic_year_filter:
            queryset = queryset.filter(academic_year_id=academic_year_filter)
        
        if section_filter:
            queryset = queryset.filter(section__icontains=section_filter)
        
        return queryset.distinct().order_by('academic_year', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ClassSearchForm(self.request.GET)
        return context


class ClassDetailView(LoginRequiredMixin, InstitutionAccessMixin, DetailView):
    model = Class
    template_name = 'students/class_detail_modern.html'
    context_object_name = 'class_obj'
    
    def get_queryset(self):
        queryset = Class.objects.select_related('academic_year__institution').prefetch_related('students__user')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(students__user=user)
        if user.user_type == 'parent':
            return queryset.filter(students__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(schedules__teacher__user=user).distinct()
        return self.scope_institution_queryset(queryset, 'academic_year__institution_id')


class ClassCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Class
    form_class = ClassForm
    template_name = 'students/class_form.html'
    permission_required = 'students.add_class'
    success_url = reverse_lazy('students:class_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Class created successfully!')
        return super().form_valid(form)


class ClassUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Class
    form_class = ClassForm
    template_name = 'students/class_form.html'
    permission_required = 'students.change_class'
    
    def get_success_url(self):
        return reverse('students:class_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Class updated successfully!')
        return super().form_valid(form)


class ClassDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Class
    template_name = 'students/class_confirm_delete.html'
    permission_required = 'students.delete_class'
    context_object_name = 'class_obj'
    success_url = reverse_lazy('students:class_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Class deleted successfully!')
        return super().delete(request, *args, **kwargs)


class StudentClassPlacementView(LoginRequiredMixin, AdminRequiredMixin, FormView):
    template_name = 'students/class_placement.html'
    form_class = StudentClassPlacementForm
    success_url = reverse_lazy('students:class_placement')

    def get_institution_ids(self):
        if is_platform_admin(self.request.user):
            return None
        return user_institution_ids(self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['institution_ids'] = self.get_institution_ids()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution_ids = self.get_institution_ids()
        students = Student.objects.select_related('user', 'current_class__academic_year__institution').filter(is_active=True)
        classes = Class.objects.select_related('academic_year__institution').prefetch_related('students').filter(is_active=True)
        if institution_ids is not None:
            students = students.filter(current_class__academic_year__institution_id__in=institution_ids)
            classes = classes.filter(academic_year__institution_id__in=institution_ids)
        context['recent_students'] = students.order_by('-updated_at')[:10]
        context['classes'] = classes.order_by('academic_year__institution__name', 'display_name')
        return context

    def form_valid(self, form):
        student = form.save()
        messages.success(
            self.request,
            f'{student.user.get_full_name()} assigned to {student.current_class.display_name}.'
        )
        return super().form_valid(form)


class ParentListView(LoginRequiredMixin, InstitutionAccessMixin, ListView):
    model = Parent
    template_name = 'students/parent_list.html'
    context_object_name = 'parents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Parent.objects.select_related('user', 'student__user', 'student__current_class__academic_year__institution')
        user = self.request.user
        if not is_platform_admin(user):
            institution_ids = user_institution_ids(user)
            if user.user_type == 'parent':
                queryset = queryset.filter(user=user)
            elif user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif institution_ids:
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
            else:
                queryset = queryset.none()
        
        # Apply search filters
        search = self.request.GET.get('search')
        relationship_filter = self.request.GET.get('relationship_filter')
        student_filter = self.request.GET.get('student_filter')
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(student__user__first_name__icontains=search) |
                Q(student__user__last_name__icontains=search) |
                Q(student__student_id__icontains=search)
            )
        
        if relationship_filter:
            queryset = queryset.filter(relationship=relationship_filter)
        
        if student_filter:
            queryset = queryset.filter(student_id=student_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ParentSearchForm(self.request.GET)
        return context


class ParentDetailView(LoginRequiredMixin, InstitutionAccessMixin, DetailView):
    model = Parent
    template_name = 'students/parent_detail.html'
    context_object_name = 'parent'
    
    def get_queryset(self):
        queryset = Parent.objects.select_related(
            'user', 'student__user', 'student__current_class__academic_year__institution'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        institution_ids = user_institution_ids(user)
        if user.user_type == 'parent':
            return queryset.filter(user=user)
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if institution_ids:
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
        return queryset.none()


class ParentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Parent
    form_class = ParentForm
    template_name = 'students/parent_form.html'
    permission_required = 'students.add_parent'
    success_url = reverse_lazy('students:parent_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Parent created successfully!')
        return super().form_valid(form)


class ParentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Parent
    form_class = ParentForm
    template_name = 'students/parent_form.html'
    permission_required = 'students.change_parent'
    
    def get_success_url(self):
        return reverse('students:parent_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Parent updated successfully!')
        return super().form_valid(form)


class ParentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Parent
    template_name = 'students/parent_confirm_delete.html'
    permission_required = 'students.delete_parent'
    success_url = reverse_lazy('students:parent_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Parent deleted successfully!')
        return super().delete(request, *args, **kwargs)


# AJAX Views
@login_required
def get_students_by_class(request):
    class_id = request.GET.get('class_id')
    if class_id:
        students = scope_students_for_request(
            request,
            Student.objects.filter(current_class_id=class_id, is_active=True)
        )
        data = [{'id': student.id, 'name': student.user.get_full_name(), 'student_id': student.student_id} for student in students]
        return JsonResponse({'students': data})
    return JsonResponse({'students': []})


@login_required
def get_classes_by_academic_year(request):
    academic_year_id = request.GET.get('academic_year_id')
    if academic_year_id:
        classes = scope_institution_for_request(
            request,
            Class.objects.filter(academic_year_id=academic_year_id, is_active=True),
            'academic_year__institution_id'
        )
        data = [{'id': class_obj.id, 'name': class_obj.display_name} for class_obj in classes]
        return JsonResponse({'classes': data})
    return JsonResponse({'classes': []})


@login_required
def student_statistics(request):
    # Get statistics for charts
    scoped_students = scope_students_for_request(
        request,
        Student.objects.select_related('current_class__academic_year__institution')
    )
    students_by_gender = scoped_students.values('gender').annotate(count=Count('id'))
    students_by_status = scoped_students.values('admission_status').annotate(count=Count('id'))
    students_by_class = scoped_students.values('current_class__display_name').annotate(count=Count('id'))
    
    # Recent admissions
    recent_admissions = scoped_students.order_by('-created_at')[:10]
    
    data = {
        'gender_data': list(students_by_gender),
        'status_data': list(students_by_status),
        'class_data': list(students_by_class),
        'recent_admissions': StudentSummarySerializer(recent_admissions, many=True).data
    }
    
    return JsonResponse(data)
