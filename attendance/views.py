from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from datetime import datetime, timedelta
import json

from accounts.permissions import (
    InstitutionAccessMixin,
    IsInstitutionTeacherOrAdmin, is_platform_admin, user_can_access_institution,
    user_institution_ids, is_admin_user
)
from .models import Attendance, ClassAttendance, TeacherAttendance, LeaveRequest
from .forms import (
    AttendanceForm, BulkAttendanceForm, StudentAttendanceForm, ClassAttendanceForm,
    TeacherAttendanceForm, LeaveRequestForm, LeaveApprovalForm, AttendanceSearchForm,
    LeaveRequestSearchForm
)
from .serializers import (
    AttendanceSerializer, AttendanceCreateSerializer, BulkAttendanceSerializer,
    ClassAttendanceSerializer, ClassAttendanceCreateSerializer, TeacherAttendanceSerializer,
    TeacherAttendanceCreateSerializer, LeaveRequestSerializer, LeaveRequestCreateSerializer,
    LeaveApprovalSerializer, AttendanceSummarySerializer, LeaveRequestSummarySerializer,
    AttendanceReportSerializer
)
from students.models import Student, Class
from teachers.models import Teacher


def get_teacher_profile(user):
    return getattr(user, 'teacher_profile', None)


def get_student_profile(user):
    return getattr(user, 'student_profile', None)


def ensure_user_can_access_student(user, student):
    institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
    if not user_can_access_institution(user, institution_id):
        raise PermissionDenied('You cannot modify attendance for this institution.')
    if (
        user.user_type == 'teacher'
        and student.current_class is not None
        and not student.current_class.schedules.filter(teacher__user=user).exists()
    ):
        raise PermissionDenied('You cannot modify attendance for students outside your assigned classes.')


# API Viewsets
class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_create']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AttendanceCreateSerializer
        return AttendanceSerializer
    
    def get_queryset(self):
        queryset = Attendance.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'marked_by__user'
        )
        user = self.request.user
        if not is_platform_admin(user):
            institution_ids = user_institution_ids(user)
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            elif user.user_type == 'teacher':
                queryset = queryset.filter(student__current_class__schedules__teacher__user=user).distinct()
            elif institution_ids:
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
            else:
                queryset = queryset.none()
        student_id = self.request.query_params.get('student', None)
        date = self.request.query_params.get('date', None)
        status = self.request.query_params.get('status', None)
        
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if date:
            queryset = queryset.filter(date=date)
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = BulkAttendanceSerializer(data=request.data)
        if serializer.is_valid():
            teacher = get_teacher_profile(request.user)
            if teacher is None:
                return Response({'detail': 'Teacher profile required.'}, status=status.HTTP_403_FORBIDDEN)

            class_obj = Class.objects.get(id=serializer.validated_data['class_obj'])
            date = serializer.validated_data['date']
            attendances = serializer.validated_data['attendances']
            
            created_attendances = []
            for attendance_data in attendances:
                student = Student.objects.select_related('current_class__academic_year__institution').get(id=attendance_data['student_id'])
                ensure_user_can_access_student(request.user, student)
                attendance, created = Attendance.objects.get_or_create(
                    student=student,
                    date=date,
                    defaults={
                        'status': attendance_data['status'],
                        'remarks': attendance_data.get('remarks', ''),
                        'marked_by': teacher
                    }
                )
                if not created:
                    attendance.status = attendance_data['status']
                    attendance.remarks = attendance_data.get('remarks', '')
                    attendance.save()
                created_attendances.append(attendance)
            
            return Response({
                'message': f'Successfully marked attendance for {len(created_attendances)} students',
                'attendances': AttendanceSerializer(created_attendances, many=True).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        ensure_user_can_access_student(self.request.user, student)
        serializer.save(marked_by=get_teacher_profile(self.request.user))

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        ensure_user_can_access_student(self.request.user, student)
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        queryset = self.get_queryset()
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        summary = queryset.aggregate(
            total_students=Count('id'),
            present_count=Count('id', filter=Q(status='present')),
            absent_count=Count('id', filter=Q(status='absent')),
            late_count=Count('id', filter=Q(status='late'))
        )
        
        if summary['total_students'] > 0:
            summary['attendance_percentage'] = (summary['present_count'] / summary['total_students']) * 100
        else:
            summary['attendance_percentage'] = 0
        
        return Response(summary)


class ClassAttendanceViewSet(viewsets.ModelViewSet):
    queryset = ClassAttendance.objects.all()
    serializer_class = ClassAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ClassAttendanceCreateSerializer
        return ClassAttendanceSerializer

    def get_queryset(self):
        queryset = ClassAttendance.objects.select_related(
            'class_obj__academic_year__institution', 'marked_by__user'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(class_obj__schedules__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def perform_create(self, serializer):
        class_obj = serializer.validated_data.get('class_obj')
        if not user_can_access_institution(self.request.user, getattr(getattr(class_obj, 'academic_year', None), 'institution_id', None)):
            raise PermissionDenied('You cannot create class attendance for this institution.')
        serializer.save(marked_by=get_teacher_profile(self.request.user))

    def perform_update(self, serializer):
        class_obj = serializer.validated_data.get('class_obj', serializer.instance.class_obj)
        if not user_can_access_institution(self.request.user, getattr(getattr(class_obj, 'academic_year', None), 'institution_id', None)):
            raise PermissionDenied('You cannot move class attendance to this institution.')
        serializer.save()


class TeacherAttendanceViewSet(viewsets.ModelViewSet):
    queryset = TeacherAttendance.objects.all()
    serializer_class = TeacherAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TeacherAttendanceCreateSerializer
        return TeacherAttendanceSerializer

    def get_queryset(self):
        queryset = TeacherAttendance.objects.select_related('teacher__user')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(teacher__user=user)
        institution_ids = user_institution_ids(user)
        return queryset.filter(teacher__user__institution_memberships__institution_id__in=institution_ids).distinct() if institution_ids else queryset.none()


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ['approve', 'reject', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LeaveRequestCreateSerializer
        elif self.action in ['approve', 'reject']:
            return LeaveApprovalSerializer
        return LeaveRequestSerializer

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'teacher__user', 'approved_by__user'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher__user=user) | Q(student__current_class__schedules__teacher__user=user)).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        leave_request = self.get_object()
        serializer = LeaveApprovalSerializer(leave_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Leave request approved successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        leave_request = self.get_object()
        serializer = LeaveApprovalSerializer(leave_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Leave request rejected successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Web Views
class MyAttendanceView(LoginRequiredMixin, TemplateView):
    template_name = 'attendance/my_attendance.html'

    def get_queryset(self):
        queryset = Attendance.objects.select_related(
            'student__user',
            'student__current_class__academic_year__institution',
            'marked_by__user',
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user).distinct()
        if user.user_type == 'teacher':
            return queryset.filter(student__current_class__schedules__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attendances = self.get_queryset().order_by('-date')
        total = attendances.count()
        present = attendances.filter(status=Attendance.AttendanceStatus.PRESENT).count()
        late = attendances.filter(status=Attendance.AttendanceStatus.LATE).count()
        absent = attendances.filter(status=Attendance.AttendanceStatus.ABSENT).count()
        half_day = attendances.filter(status=Attendance.AttendanceStatus.HALF_DAY).count()
        context.update({
            'attendances': attendances[:30],
            'total_days': total,
            'present_days': present,
            'late_days': late,
            'absent_days': absent,
            'half_days': half_day,
            'attendance_rate': round(((present + late + half_day) / total) * 100, 1) if total else None,
        })
        return context


class AttendanceListView(LoginRequiredMixin, InstitutionAccessMixin, ListView):
    model = Attendance
    template_name = 'attendance/attendance_list.html'
    context_object_name = 'attendances'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Attendance.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'marked_by__user'
        )
        user = self.request.user
        if not is_platform_admin(user):
            institution_ids = user_institution_ids(user)
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            elif user.user_type == 'teacher':
                queryset = queryset.filter(student__current_class__schedules__teacher__user=user).distinct()
            elif institution_ids:
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
            else:
                queryset = queryset.none()
        
        # Apply filters
        form = AttendanceSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(date__gte=form.cleaned_data['date_from'])
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(date__lte=form.cleaned_data['date_to'])
            if form.cleaned_data.get('class_obj'):
                queryset = queryset.filter(student__current_class=form.cleaned_data['class_obj'])
            if form.cleaned_data.get('student'):
                queryset = queryset.filter(student=form.cleaned_data['student'])
            if form.cleaned_data.get('status'):
                queryset = queryset.filter(status=form.cleaned_data['status'])
        
        return queryset.order_by('-date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = AttendanceSearchForm(self.request.GET)
        return context


class AttendanceDetailView(LoginRequiredMixin, InstitutionAccessMixin, DetailView):
    model = Attendance
    template_name = 'attendance/attendance_detail_modern.html'
    context_object_name = 'attendance'

    def get_queryset(self):
        queryset = Attendance.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution', 'marked_by__user'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        institution_ids = user_institution_ids(user)
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(student__current_class__schedules__teacher__user=user).distinct()
        if institution_ids:
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
        return queryset.none()


class AttendanceCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Attendance
    form_class = AttendanceForm
    template_name = 'attendance/attendance_form.html'
    success_url = reverse_lazy('attendance:attendance_list')
    
    def test_func(self):
        return get_teacher_profile(self.request.user) is not None
    
    def form_valid(self, form):
        ensure_user_can_access_student(self.request.user, form.cleaned_data['student'])
        form.instance.marked_by = get_teacher_profile(self.request.user)
        messages.success(self.request, 'Attendance marked successfully.')
        return super().form_valid(form)


class AttendanceUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Attendance
    form_class = AttendanceForm
    template_name = 'attendance/attendance_form.html'
    success_url = reverse_lazy('attendance:attendance_list')
    
    def test_func(self):
        attendance = self.get_object()
        teacher = get_teacher_profile(self.request.user)
        if is_admin_user(self.request.user):
            return True
        return (
            teacher is not None
            and attendance.student.current_class is not None
            and attendance.student.current_class.schedules.filter(teacher=teacher).exists()
        )
    
    def form_valid(self, form):
        ensure_user_can_access_student(self.request.user, form.cleaned_data['student'])
        messages.success(self.request, 'Attendance updated successfully.')
        return super().form_valid(form)


class BulkAttendanceView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = BulkAttendanceForm
    template_name = 'attendance/bulk_attendance.html'
    success_url = reverse_lazy('attendance:attendance_list')
    
    def test_func(self):
        return get_teacher_profile(self.request.user) is not None or is_admin_user(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            form = self.get_form()
            if form.is_valid():
                class_obj = form.cleaned_data['class_obj']
                students = Student.objects.filter(current_class=class_obj)
                context['students'] = students
        return context
    
    def form_valid(self, form):
        class_obj = form.cleaned_data['class_obj']
        date = form.cleaned_data['date']
        if self.request.user.user_type == 'teacher' and not class_obj.schedules.filter(teacher__user=self.request.user).exists():
            raise PermissionDenied('You cannot mark attendance for classes you do not teach.')
        students = Student.objects.filter(current_class=class_obj)
        
        # Get attendance data from form
        attendances_data = []
        for student in students:
            student_id = str(student.id)
            status_key = f'status_{student_id}'
            remarks_key = f'remarks_{student_id}'
            
            if status_key in self.request.POST:
                attendances_data.append({
                    'student_id': student.id,
                    'status': self.request.POST[status_key],
                    'remarks': self.request.POST.get(remarks_key, '')
                })
        
        # Create or update attendance records
        created_count = 0
        for data in attendances_data:
            attendance, created = Attendance.objects.get_or_create(
                student_id=data['student_id'],
                date=date,
                defaults={
                    'status': data['status'],
                    'remarks': data['remarks'],
                    'marked_by': get_teacher_profile(self.request.user)
                }
            )
            if not created:
                attendance.status = data['status']
                attendance.remarks = data['remarks']
                attendance.save()
            else:
                created_count += 1
        
        messages.success(self.request, f'Successfully marked attendance for {len(attendances_data)} students.')
        return super().form_valid(form)


class LeaveRequestListView(LoginRequiredMixin, InstitutionAccessMixin, ListView):
    model = LeaveRequest
    template_name = 'attendance/leave_request_list.html'
    context_object_name = 'leave_requests'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'teacher__user', 'approved_by__user'
        )
        
        user = self.request.user
        if is_admin_user(user):
            pass
        elif user.user_type == 'student':
            queryset = queryset.filter(student__user=user)
        elif user.user_type == 'parent':
            queryset = queryset.filter(student__parents__user=user)
        elif user.user_type == 'teacher':
            queryset = queryset.filter(Q(teacher__user=user) | Q(student__current_class__schedules__teacher__user=user)).distinct()
        else:
            institution_ids = user_institution_ids(user)
            queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        # Apply search filters
        form = LeaveRequestSearchForm(self.request.GET)
        if form.is_valid():
            if form.cleaned_data.get('date_from'):
                queryset = queryset.filter(start_date__gte=form.cleaned_data['date_from'])
            if form.cleaned_data.get('date_to'):
                queryset = queryset.filter(end_date__lte=form.cleaned_data['date_to'])
            if form.cleaned_data.get('leave_type'):
                queryset = queryset.filter(leave_type=form.cleaned_data['leave_type'])
            if form.cleaned_data.get('status'):
                queryset = queryset.filter(status=form.cleaned_data['status'])
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = LeaveRequestSearchForm(self.request.GET)
        return context


class LeaveRequestDetailView(LoginRequiredMixin, DetailView):
    model = LeaveRequest
    template_name = 'attendance/leave_request_detail_modern.html'
    context_object_name = 'leave_request'

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'teacher__user', 'approved_by__user'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        institution_ids = user_institution_ids(user)
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher__user=user) | Q(student__current_class__schedules__teacher__user=user)).distinct()
        if institution_ids:
            return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids)
        return queryset.none()


class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'attendance/leave_request_form.html'
    success_url = reverse_lazy('attendance:leave_request_list')
    
    def form_valid(self, form):
        student = get_student_profile(self.request.user)
        teacher = get_teacher_profile(self.request.user)
        if student is not None:
            form.instance.student = student
        elif teacher is not None:
            form.instance.teacher = teacher
        else:
            messages.error(self.request, 'Invalid user type.')
            return self.form_invalid(form)
        
        messages.success(self.request, 'Leave request submitted successfully.')
        return super().form_valid(form)


class LeaveRequestUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'attendance/leave_request_form.html'
    success_url = reverse_lazy('attendance:leave_request_list')
    
    def test_func(self):
        leave_request = self.get_object()
        if is_admin_user(self.request.user):
            return True
        student = get_student_profile(self.request.user)
        teacher = get_teacher_profile(self.request.user)
        if student is not None:
            return leave_request.student == student
        elif teacher is not None:
            return leave_request.teacher == teacher
        return False
    
    def form_valid(self, form):
        messages.success(self.request, 'Leave request updated successfully.')
        return super().form_valid(form)


class LeaveApprovalView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = LeaveRequest
    form_class = LeaveApprovalForm
    template_name = 'attendance/leave_approval_modern.html'
    success_url = reverse_lazy('attendance:leave_request_list')
    
    def test_func(self):
        return is_admin_user(self.request.user) or get_teacher_profile(self.request.user) is not None

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'teacher__user', 'approved_by__user'
        )
        user = self.request.user
        if is_admin_user(user):
            return queryset
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher__user=user) | Q(student__current_class__schedules__teacher__user=user)).distinct()
        return queryset.none()
    
    def form_valid(self, form):
        if form.cleaned_data['status'] == LeaveRequest.LeaveStatus.APPROVED:
            form.instance.approved_by = get_teacher_profile(self.request.user)
            form.instance.approved_at = timezone.now()
            messages.success(self.request, 'Leave request approved successfully.')
        else:
            messages.success(self.request, 'Leave request updated successfully.')
        
        return super().form_valid(form)


# Dashboard and Reports
@login_required
def attendance_dashboard(request):
    today = timezone.now().date()
    
    # Get attendance statistics
    teacher = get_teacher_profile(request.user)
    student = get_student_profile(request.user)

    if teacher is not None:
        # Teacher dashboard
        classes = Class.objects.filter(schedules__teacher=teacher).distinct()
        today_attendance = ClassAttendance.objects.filter(
            class_obj__in=classes, date=today
        ).first()
        
        context = {
            'today_attendance': today_attendance,
            'classes': classes,
            'recent_attendances': Attendance.objects.filter(
                student__current_class__in=classes
            ).order_by('-date')[:10]
        }
    elif student is not None:
        # Student dashboard
        today_attendance = Attendance.objects.filter(student=student, date=today).first()
        
        # Monthly attendance summary
        month_start = today.replace(day=1)
        monthly_attendance = Attendance.objects.filter(
            student=student, date__gte=month_start, date__lte=today
        )
        
        context = {
            'today_attendance': today_attendance,
            'monthly_attendance': monthly_attendance,
            'attendance_percentage': calculate_attendance_percentage(monthly_attendance)
        }
    else:
        # Admin dashboard
        total_students = Student.objects.count()
        today_present = Attendance.objects.filter(date=today, status='present').count()
        today_absent = Attendance.objects.filter(date=today, status='absent').count()
        
        context = {
            'total_students': total_students,
            'today_present': today_present,
            'today_absent': today_absent,
            'attendance_percentage': (today_present / total_students * 100) if total_students > 0 else 0
        }
    
    return render(request, 'attendance/dashboard.html', context)


def calculate_attendance_percentage(attendance_queryset):
    total_days = attendance_queryset.count()
    present_days = attendance_queryset.filter(status='present').count()
    
    if total_days > 0:
        return (present_days / total_days) * 100
    return 0


@login_required
def attendance_report(request):
    if request.method == 'POST':
        form = AttendanceSearchForm(request.POST)
        if form.is_valid():
            date_from = form.cleaned_data['date_from']
            date_to = form.cleaned_data['date_to']
            class_obj = form.cleaned_data['class_obj']
            
            # Generate report data
            attendances = Attendance.objects.filter(
                date__gte=date_from,
                date__lte=date_to
            )
            
            if class_obj:
                attendances = attendances.filter(student__current_class=class_obj)
            
            # Group by student and calculate statistics
            report_data = []
            students = Student.objects.filter(attendances__in=attendances).distinct()
            
            for student in students:
                student_attendances = attendances.filter(student=student)
                total_days = student_attendances.count()
                present_days = student_attendances.filter(status='present').count()
                absent_days = student_attendances.filter(status='absent').count()
                late_days = student_attendances.filter(status='late').count()
                
                attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
                
                report_data.append({
                    'student': student,
                    'total_days': total_days,
                    'present_days': present_days,
                    'absent_days': absent_days,
                    'late_days': late_days,
                    'attendance_percentage': attendance_percentage
                })
            
            context = {
                'form': form,
                'report_data': report_data,
                'date_from': date_from,
                'date_to': date_to
            }
        else:
            context = {'form': form}
    else:
        form = AttendanceSearchForm()
        context = {'form': form}
    
    return render(request, 'attendance/attendance_report.html', context)


# AJAX Views
@login_required
def get_students_for_class(request):
    class_id = request.GET.get('class_id')
    if class_id:
        students = Student.objects.filter(current_class_id=class_id)
        data = [{'id': student.id, 'name': student.user.get_full_name()} for student in students]
        return JsonResponse({'students': data})
    return JsonResponse({'students': []})


@login_required
def mark_attendance_ajax(request):
    if request.method == 'POST':
        teacher = get_teacher_profile(request.user)
        if teacher is None:
            return JsonResponse({
                'success': False,
                'message': 'Teacher profile required.'
            }, status=403)

        data = json.loads(request.body)
        student_id = data.get('student_id')
        date = data.get('date')
        status = data.get('status')
        remarks = data.get('remarks', '')
        
        try:
            student = Student.objects.get(id=student_id)
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                date=date,
                defaults={
                    'status': status,
                    'remarks': remarks,
                    'marked_by': teacher
                }
            )
            
            if not created:
                attendance.status = status
                attendance.remarks = remarks
                attendance.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Attendance marked successfully',
                'created': created
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})
