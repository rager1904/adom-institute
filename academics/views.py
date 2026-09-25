from django.shortcuts import render, get_object_or_404, redirect
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q, Avg, Count, Max, Min, F, DecimalField, ExpressionWrapper, Value
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounts.permissions import (
    InstitutionAccessMixin,
    IsInstitutionTeacherOrAdmin, IsPlatformOrInstitutionAdmin, is_platform_admin,
    user_can_access_institution, user_institution_ids, AcademicStaffRequiredMixin,
    is_admin_user
)
from .models import (
    ExamType, Exam, ExamSubject, Grade, StudentExamResult,
    Assignment, StudentAssignment
)
from .serializers import (
    ExamTypeSerializer, ExamSerializer, ExamSubjectSerializer, GradeSerializer,
    StudentExamResultSerializer, AssignmentSerializer, StudentAssignmentSerializer,
    BulkGradeEntrySerializer, AssignmentSubmissionSerializer, AssignmentGradingSerializer,
    ExamResultSummarySerializer, AssignmentSummarySerializer
)
from .forms import ExamForm, AssignmentForm, StudentExamResultForm
from students.models import Class, Student
from attendance.models import Attendance
from library.models import DigitalResource


def get_teacher_profile(user):
    return getattr(user, 'teacher_profile', None)


def get_student_profile(user):
    return getattr(user, 'student_profile', None)


class DashboardView(InstitutionAccessMixin, TemplateView):
    template_name = 'academics/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution_ids = user_institution_ids(self.request.user)
        exams = Exam.objects.select_related('academic_year', 'class_obj', 'exam_type')
        assignments = Assignment.objects.select_related('class_obj', 'subject', 'teacher')
        if institution_ids and not is_platform_admin(self.request.user):
            exams = exams.filter(class_obj__academic_year__institution_id__in=institution_ids)
            assignments = assignments.filter(class_obj__academic_year__institution_id__in=institution_ids)

        context.update({
            'total_exams': exams.count(),
            'active_exams': exams.filter(is_active=True).count(),
            'total_assignments': assignments.count(),
            'active_assignments': assignments.filter(is_active=True).count(),
            'recent_exams': exams.order_by('-start_date')[:5],
            'upcoming_assignments': assignments.filter(is_active=True).order_by('due_date')[:5],
            'graded_submissions': StudentAssignment.objects.filter(marks_obtained__isnull=False).count(),
        })
        return context


class CourseListView(InstitutionAccessMixin, ListView):
    model = Class
    template_name = 'academics/course_list.html'
    context_object_name = 'courses'
    paginate_by = 20

    def get_queryset(self):
        queryset = Class.objects.select_related('academic_year__institution').prefetch_related('students')
        user = self.request.user
        if is_platform_admin(user):
            return queryset.order_by('display_name')
        if user.user_type == 'student':
            return queryset.filter(students__user=user).distinct().order_by('display_name')
        if user.user_type == 'parent':
            return queryset.filter(students__parents__user=user).distinct().order_by('display_name')
        if user.user_type == 'teacher':
            return queryset.filter(Q(assignments__teacher__user=user) | Q(schedules__teacher__user=user)).distinct().order_by('display_name')
        return self.scope_institution_queryset(queryset, 'academic_year__institution_id').order_by('display_name')


class CourseDetailView(InstitutionAccessMixin, DetailView):
    model = Class
    template_name = 'academics/course_detail.html'
    context_object_name = 'course'

    def get_queryset(self):
        return CourseListView.get_queryset(self)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        assignments = Assignment.objects.filter(class_obj=course).select_related('subject', 'teacher__user')
        assignment_ids = assignments.values_list('id', flat=True)
        submitted_count = StudentAssignment.objects.filter(assignment_id__in=assignment_ids).count()
        expected_submissions = course.students.count() * assignments.count()
        attendance_counts = Attendance.objects.filter(student__current_class=course).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status=Attendance.AttendanceStatus.PRESENT)),
        )
        subject_names = set(assignments.values_list('subject__name', flat=True))
        subject_names.update(
            ExamSubject.objects.filter(exam__class_obj=course).values_list('subject__name', flat=True)
        )
        resources = DigitalResource.objects.filter(is_active=True).filter(
            Q(subject__in=subject_names) | Q(course_links__subject__in=subject_names)
        ).distinct().order_by('-created_at')[:10]
        attendance_total = attendance_counts['total'] or 0
        attendance_present = attendance_counts['present'] or 0
        context['exams'] = Exam.objects.filter(class_obj=course).select_related('exam_type').order_by('-start_date')[:10]
        context['assignments'] = assignments.order_by('-created_at')[:10]
        context['resources'] = resources
        context['student_count'] = course.students.count()
        context['attendance_rate'] = round((attendance_present / attendance_total) * 100, 1) if attendance_total else 0
        context['assignment_progress'] = round((submitted_count / expected_submissions) * 100, 1) if expected_submissions else 0
        return context


def percentage_expression():
    return ExpressionWrapper(
        F('marks_obtained') * Value(
            Decimal('100.00'),
            output_field=DecimalField(max_digits=5, decimal_places=2),
        ) / F('exam_subject__max_marks'),
        output_field=DecimalField(max_digits=6, decimal_places=2),
    )


def scoped_academic_queryset(request, queryset, institution_lookup):
    user = request.user
    if is_platform_admin(user):
        return queryset
    institution_ids = user_institution_ids(user)
    if institution_ids:
        return queryset.filter(**{f'{institution_lookup}__in': institution_ids}).distinct()
    return queryset.none()


def ensure_user_can_access_institution(user, institution_id, message):
    if not user_can_access_institution(user, institution_id):
        raise PermissionDenied(message)


# API Viewsets
class ExamTypeViewSet(viewsets.ModelViewSet):
    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'weightage', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.select_related('exam_type', 'academic_year', 'class_obj').all()
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['exam_type', 'academic_year', 'class_obj', 'is_active']
    search_fields = ['name', 'exam_type__name', 'class_obj__name']
    ordering_fields = ['name', 'start_date', 'end_date', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Exam.objects.select_related(
            'exam_type', 'academic_year', 'academic_year__institution', 'class_obj'
        ).all()
        return scoped_academic_queryset(self.request, queryset, 'academic_year__institution_id')

    def perform_create(self, serializer):
        academic_year = serializer.validated_data.get('academic_year')
        ensure_user_can_access_institution(
            self.request.user,
            getattr(academic_year, 'institution_id', None),
            'You cannot create exams for this institution.',
        )
        serializer.save()

    def perform_update(self, serializer):
        academic_year = serializer.validated_data.get('academic_year', serializer.instance.academic_year)
        ensure_user_can_access_institution(
            self.request.user,
            getattr(academic_year, 'institution_id', None),
            'You cannot move exams to this institution.',
        )
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def results_summary(self, request, pk=None):
        exam = self.get_object()
        results = StudentExamResult.objects.filter(exam_subject__exam=exam).annotate(
            percentage_value=percentage_expression()
        )
        total_results = results.count()
        grade_distribution = {
            item['grade__name'] or 'Ungraded': item['count']
            for item in results.values('grade__name').annotate(count=Count('id')).order_by('grade__name')
        }
        
        summary = {
            'exam_id': exam.id,
            'total_students': total_results,
            'passed_students': results.filter(marks_obtained__gte=F('exam_subject__passing_marks')).count(),
            'failed_students': results.filter(marks_obtained__lt=F('exam_subject__passing_marks')).count(),
            'average_percentage': results.aggregate(avg=Avg('percentage_value'))['avg'] or 0,
            'highest_percentage': results.aggregate(max=Max('percentage_value'))['max'] or 0,
            'lowest_percentage': results.aggregate(min=Min('percentage_value'))['min'] or 0,
            'grade_distribution': grade_distribution,
        }
        
        serializer = ExamResultSummarySerializer(summary)
        return Response(serializer.data)


class ExamSubjectViewSet(viewsets.ModelViewSet):
    queryset = ExamSubject.objects.select_related('exam', 'subject').all()
    serializer_class = ExamSubjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['exam', 'subject', 'exam_date']
    search_fields = ['exam__name', 'subject__name']
    ordering_fields = ['exam_date', 'duration', 'max_marks']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = ExamSubject.objects.select_related(
            'exam__academic_year__institution', 'subject'
        ).all()
        return scoped_academic_queryset(self.request, queryset, 'exam__academic_year__institution_id')

    def perform_create(self, serializer):
        exam = serializer.validated_data.get('exam')
        ensure_user_can_access_institution(
            self.request.user,
            getattr(getattr(exam, 'academic_year', None), 'institution_id', None),
            'You cannot create exam subjects for this institution.',
        )
        serializer.save()

    def perform_update(self, serializer):
        exam = serializer.validated_data.get('exam', serializer.instance.exam)
        ensure_user_can_access_institution(
            self.request.user,
            getattr(getattr(exam, 'academic_year', None), 'institution_id', None),
            'You cannot move exam subjects to this institution.',
        )
        serializer.save()


class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['min_marks', 'max_marks', 'grade_point']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsPlatformOrInstitutionAdmin()]
        return super().get_permissions()


class StudentExamResultViewSet(viewsets.ModelViewSet):
    queryset = StudentExamResult.objects.select_related(
        'student__user', 'exam_subject__exam', 'exam_subject__subject', 'grade', 'created_by__user'
    ).all()
    serializer_class = StudentExamResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['exam_subject__exam', 'exam_subject__subject', 'grade']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'exam_subject__exam__name']
    ordering_fields = ['marks_obtained', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'bulk_grade_entry']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = StudentExamResult.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'exam_subject__exam', 'exam_subject__subject', 'grade', 'created_by__user'
        ).all()
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(student__current_class__schedules__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        ensure_user_can_access_institution(
            self.request.user,
            institution_id,
            'You cannot create results for this institution.',
        )
        serializer.save()

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        ensure_user_can_access_institution(
            self.request.user,
            institution_id,
            'You cannot move results to this institution.',
        )
        serializer.save()
    
    @action(detail=False, methods=['post'])
    def bulk_grade_entry(self, request):
        serializer = BulkGradeEntrySerializer(data=request.data)
        if serializer.is_valid():
            teacher = get_teacher_profile(request.user)
            if teacher is None:
                return Response({'detail': 'Teacher profile required.'}, status=status.HTTP_403_FORBIDDEN)

            exam_subject_id = serializer.validated_data['exam_subject_id']
            grades = serializer.validated_data['grades']
            
            exam_subject = get_object_or_404(ExamSubject, id=exam_subject_id)
            created_results = []
            
            for grade_data in grades:
                student_id = grade_data['student_id']
                marks_obtained = grade_data['marks_obtained']
                
                from students.models import Student
                student = get_object_or_404(
                    Student.objects.select_related('current_class__academic_year__institution'),
                    id=student_id,
                )
                ensure_user_can_access_institution(
                    request.user,
                    getattr(getattr(student.current_class, 'academic_year', None), 'institution_id', None),
                    'You cannot grade students outside your institution.',
                )

                result, created = StudentExamResult.objects.get_or_create(
                    student=student,
                    exam_subject=exam_subject,
                    defaults={
                        'marks_obtained': marks_obtained,
                        'created_by': teacher
                    }
                )
                
                if not created:
                    result.marks_obtained = marks_obtained
                    result.save()
                
                created_results.append(result)
            
            return Response({
                'message': f'Successfully processed {len(created_results)} grades',
                'results_count': len(created_results)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.select_related('subject', 'class_obj', 'teacher__user').all()
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['subject', 'class_obj', 'teacher', 'is_active']
    search_fields = ['title', 'subject__name', 'class_obj__name']
    ordering_fields = ['due_date', 'max_marks', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Assignment.objects.select_related(
            'subject', 'class_obj__academic_year__institution', 'teacher__user'
        ).all()
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(class_obj__students__user=user).distinct()
        if user.user_type == 'parent':
            return queryset.filter(class_obj__students__parents__user=user).distinct()
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher__user=user) | Q(class_obj__schedules__teacher__user=user)).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def perform_create(self, serializer):
        class_obj = serializer.validated_data.get('class_obj')
        ensure_user_can_access_institution(
            self.request.user,
            getattr(getattr(class_obj, 'academic_year', None), 'institution_id', None),
            'You cannot create assignments for this institution.',
        )
        serializer.save()

    def perform_update(self, serializer):
        class_obj = serializer.validated_data.get('class_obj', serializer.instance.class_obj)
        ensure_user_can_access_institution(
            self.request.user,
            getattr(getattr(class_obj, 'academic_year', None), 'institution_id', None),
            'You cannot move assignments to this institution.',
        )
        serializer.save()
    
    @action(detail=True, methods=['get'])
    def submission_summary(self, request, pk=None):
        assignment = self.get_object()
        submissions = StudentAssignment.objects.filter(assignment=assignment)
        
        summary = {
            'assignment_id': assignment.id,
            'total_students': assignment.class_obj.students.count(),
            'submitted_students': submissions.count(),
            'pending_students': assignment.class_obj.students.count() - submissions.count(),
            'graded_submissions': submissions.filter(is_graded=True).count(),
            'average_marks': submissions.filter(is_graded=True).aggregate(avg=Avg('marks_obtained'))['avg'] or 0,
            'submission_rate': (submissions.count() / assignment.class_obj.students.count()) * 100 if assignment.class_obj.students.count() > 0 else 0,
        }
        
        serializer = AssignmentSummarySerializer(summary)
        return Response(serializer.data)


class StudentAssignmentViewSet(viewsets.ModelViewSet):
    queryset = StudentAssignment.objects.select_related(
        'student__user', 'assignment__subject', 'graded_by__user'
    ).all()
    serializer_class = StudentAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['assignment', 'is_late', 'is_graded']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'assignment__title']
    ordering_fields = ['submitted_at', 'marks_obtained', 'graded_at']
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ['grade_submission']:
            return [IsInstitutionTeacherOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = StudentAssignment.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'assignment__subject', 'graded_by__user'
        ).all()
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(assignment__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def perform_create(self, serializer):
        student = serializer.validated_data.get('student')
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        ensure_user_can_access_institution(
            self.request.user,
            institution_id,
            'You cannot submit assignments for this institution.',
        )
        serializer.save()

    def perform_update(self, serializer):
        student = serializer.validated_data.get('student', serializer.instance.student)
        institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        ensure_user_can_access_institution(
            self.request.user,
            institution_id,
            'You cannot move submissions to this institution.',
        )
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def grade_submission(self, request, pk=None):
        submission = self.get_object()
        serializer = AssignmentGradingSerializer(submission, data=request.data, partial=True)
        
        if serializer.is_valid():
            teacher = get_teacher_profile(request.user)
            if teacher is None:
                return Response({'detail': 'Teacher profile required.'}, status=status.HTTP_403_FORBIDDEN)
            serializer.save(graded_by=teacher)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Web Views
@method_decorator(login_required, name='dispatch')
class MyAcademicsView(TemplateView):
    template_name = 'academics/my_academics.html'

    def get_students(self):
        user = self.request.user
        queryset = Student.objects.select_related('user', 'current_class')
        if is_platform_admin(user) or is_admin_user(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(user=user)
        if user.user_type == 'parent':
            return queryset.filter(parents__user=user).distinct()
        if user.user_type == 'teacher':
            return queryset.filter(current_class__schedules__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        students = list(self.get_students())
        student_ids = [student.pk for student in students]
        class_ids = [student.current_class_id for student in students if student.current_class_id]
        now = timezone.now()
        today = timezone.localdate()

        assignments = Assignment.objects.filter(
            class_obj_id__in=class_ids,
        ).select_related('subject', 'class_obj', 'teacher__user').order_by('due_date')
        submissions = StudentAssignment.objects.filter(
            student_id__in=student_ids,
        ).select_related('student__user', 'assignment__subject', 'assignment__class_obj').order_by('-submitted_at')
        results = StudentExamResult.objects.filter(
            student_id__in=student_ids,
        ).select_related('student__user', 'exam_subject__exam', 'exam_subject__subject', 'grade').order_by('-created_at')
        upcoming_exams = ExamSubject.objects.filter(
            exam__class_obj_id__in=class_ids,
            exam_date__gte=today,
        ).select_related('exam', 'subject', 'exam__class_obj').order_by('exam_date')

        context.update({
            'academic_students': students,
            'upcoming_assignments': assignments.filter(due_date__gte=now)[:10],
            'past_assignments': assignments.filter(due_date__lt=now)[:5],
            'submissions': submissions[:10],
            'results': results[:10],
            'upcoming_exams': upcoming_exams[:10],
            'submitted_assignment_ids': set(submissions.values_list('assignment_id', flat=True)),
        })
        return context


@method_decorator(login_required, name='dispatch')
class GradingQueueView(AcademicStaffRequiredMixin, ListView):
    model = StudentAssignment
    template_name = 'academics/grading_queue.html'
    context_object_name = 'submissions'
    paginate_by = 25

    def get_queryset(self):
        queryset = StudentAssignment.objects.select_related(
            'student__user',
            'student__current_class__academic_year__institution',
            'assignment__subject',
            'assignment__class_obj',
            'graded_by__user',
        ).order_by('-submitted_at')
        user = self.request.user
        if is_platform_admin(user) or is_admin_user(user):
            pass
        elif user.user_type == 'teacher':
            queryset = queryset.filter(assignment__teacher__user=user)
        else:
            institution_ids = user_institution_ids(user)
            queryset = queryset.filter(
                student__current_class__academic_year__institution_id__in=institution_ids
            ) if institution_ids else queryset.none()

        status_filter = self.request.GET.get('status', 'ungraded')
        if status_filter == 'graded':
            queryset = queryset.filter(marks_obtained__isnull=False)
        elif status_filter == 'all':
            pass
        else:
            queryset = queryset.filter(marks_obtained__isnull=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_queryset = StudentAssignment.objects.select_related('assignment__teacher__user')
        user = self.request.user
        if user.user_type == 'teacher':
            base_queryset = base_queryset.filter(assignment__teacher__user=user)
        context['status_filter'] = self.request.GET.get('status', 'ungraded')
        context['ungraded_count'] = base_queryset.filter(marks_obtained__isnull=True).count()
        context['graded_count'] = base_queryset.filter(marks_obtained__isnull=False).count()
        return context


@method_decorator(login_required, name='dispatch')
class ExamListView(InstitutionAccessMixin, ListView):
    model = Exam
    template_name = 'academics/exam_list.html'
    context_object_name = 'exams'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Exam.objects.select_related('exam_type', 'academic_year__institution', 'class_obj').all()
        user = self.request.user
        if is_platform_admin(user):
            pass
        elif user.user_type == 'student':
            queryset = queryset.filter(class_obj__students__user=user)
        elif user.user_type == 'parent':
            queryset = queryset.filter(class_obj__students__parents__user=user)
        elif user.user_type == 'teacher':
            queryset = queryset.filter(class_obj__schedules__teacher__user=user)
        else:
            queryset = self.scope_institution_queryset(queryset, 'academic_year__institution_id')
        
        # Filter by search query
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(exam_type__name__icontains=q) |
                Q(class_obj__name__icontains=q)
            )
        
        # Filter by exam type
        exam_type = self.request.GET.get('exam_type')
        if exam_type:
            queryset = queryset.filter(exam_type_id=exam_type)
        
        return queryset.distinct().order_by('-start_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_types'] = ExamType.objects.filter(is_active=True)
        return context


@method_decorator(login_required, name='dispatch')
class ExamDetailView(InstitutionAccessMixin, DetailView):
    model = Exam
    template_name = 'academics/exam_detail.html'
    context_object_name = 'exam'

    def get_queryset(self):
        queryset = Exam.objects.select_related('exam_type', 'academic_year__institution', 'class_obj')
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(class_obj__students__user=user)
        if user.user_type == 'parent':
            return queryset.filter(class_obj__students__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(class_obj__schedules__teacher__user=user).distinct()
        return self.scope_institution_queryset(queryset, 'academic_year__institution_id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_subjects'] = self.object.exam_subjects.select_related('subject').all()
        results = StudentExamResult.objects.filter(
            exam_subject__exam=self.object
        ).select_related('student__user', 'exam_subject__subject', 'grade')
        user = self.request.user
        if user.user_type == 'student':
            results = results.filter(student__user=user)
        elif user.user_type == 'parent':
            results = results.filter(student__parents__user=user)
        elif user.user_type == 'teacher':
            results = results.filter(exam_subject__exam__class_obj__schedules__teacher__user=user).distinct()
        context['results'] = results
        return context


@method_decorator(login_required, name='dispatch')
class ExamCreateView(AcademicStaffRequiredMixin, CreateView):
    model = Exam
    form_class = ExamForm
    template_name = 'academics/exam_form.html'
    success_url = reverse_lazy('academics:exam_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Exam created successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class ExamUpdateView(AcademicStaffRequiredMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = 'academics/exam_form.html'
    success_url = reverse_lazy('academics:exam_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Exam updated successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AssignmentListView(InstitutionAccessMixin, ListView):
    model = Assignment
    template_name = 'academics/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Assignment.objects.select_related(
            'subject', 'class_obj__academic_year__institution', 'teacher__user'
        ).all()
        user = self.request.user
        if not is_platform_admin(user):
            if user.user_type == 'student':
                queryset = queryset.filter(class_obj__students__user=user).distinct()
            elif user.user_type == 'parent':
                queryset = queryset.filter(class_obj__students__parents__user=user).distinct()
            elif user.user_type == 'teacher':
                queryset = queryset.filter(Q(teacher__user=user) | Q(class_obj__schedules__teacher__user=user)).distinct()
            else:
                institution_ids = user_institution_ids(user)
                queryset = queryset.filter(class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        # Filter by search query
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(subject__name__icontains=q) |
                Q(class_obj__name__icontains=q)
            )
        
        # Filter by subject
        subject = self.request.GET.get('subject')
        if subject:
            queryset = queryset.filter(subject_id=subject)
        
        return queryset.order_by('-due_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subjects'] = self.model.objects.values_list('subject__name', flat=True).distinct()
        return context


@method_decorator(login_required, name='dispatch')
class AssignmentDetailView(InstitutionAccessMixin, DetailView):
    model = Assignment
    template_name = 'academics/assignment_detail.html'
    context_object_name = 'assignment'

    def get_queryset(self):
        queryset = Assignment.objects.select_related(
            'subject', 'class_obj__academic_year__institution', 'teacher__user'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(class_obj__students__user=user).distinct()
        if user.user_type == 'parent':
            return queryset.filter(class_obj__students__parents__user=user).distinct()
        if user.user_type == 'teacher':
            return queryset.filter(Q(teacher__user=user) | Q(class_obj__schedules__teacher__user=user)).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submissions = self.object.student_submissions.select_related(
            'student__user', 'graded_by__user'
        )
        user = self.request.user
        if user.user_type == 'student':
            submissions = submissions.filter(student__user=user)
        elif user.user_type == 'parent':
            submissions = submissions.filter(student__parents__user=user)
        elif user.user_type == 'teacher':
            submissions = submissions.filter(Q(assignment__teacher__user=user) | Q(assignment__class_obj__schedules__teacher__user=user)).distinct()
        context['submissions'] = submissions
        return context


@method_decorator(login_required, name='dispatch')
class AssignmentCreateView(AcademicStaffRequiredMixin, CreateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'academics/assignment_form.html'
    success_url = reverse_lazy('academics:assignment_list')
    
    def form_valid(self, form):
        teacher = get_teacher_profile(self.request.user)
        if teacher is None:
            messages.error(self.request, 'Teacher profile required to create assignments.')
            return self.form_invalid(form)
        form.instance.teacher = teacher
        messages.success(self.request, 'Assignment created successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AssignmentUpdateView(AcademicStaffRequiredMixin, UpdateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'academics/assignment_form.html'
    success_url = reverse_lazy('academics:assignment_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated successfully!')
        return super().form_valid(form)


@login_required
def grade_entry(request, exam_subject_id):
    teacher = get_teacher_profile(request.user)
    if teacher is None:
        messages.error(request, 'Teacher profile required to enter grades.')
        return redirect('academics:exam_detail', pk=exam_subject.exam.id) if 'exam_subject' in locals() else redirect('academics:exam_list')

    exam_subject = get_object_or_404(ExamSubject, id=exam_subject_id)
    students = exam_subject.exam.class_obj.students.all()
    
    if request.method == 'POST':
        for student in students:
            marks_obtained = request.POST.get(f'marks_{student.id}')
            if marks_obtained:
                result, created = StudentExamResult.objects.get_or_create(
                    student=student,
                    exam_subject=exam_subject,
                    defaults={
                        'marks_obtained': marks_obtained,
                        'created_by': teacher
                    }
                )
                if not created:
                    result.marks_obtained = marks_obtained
                    result.save()
        
        messages.success(request, 'Grades saved successfully!')
        return redirect('academics:exam_detail', pk=exam_subject.exam.id)
    
    context = {
        'exam_subject': exam_subject,
        'students': students,
        'results': StudentExamResult.objects.filter(exam_subject=exam_subject)
    }
    return render(request, 'academics/grade_entry.html', context)


@login_required
def assignment_submission(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = get_student_profile(request.user)
    if student is None:
        messages.error(request, 'Student profile required to submit assignments.')
        return redirect('academics:assignment_detail', pk=assignment_id)
    
    if request.method == 'POST':
        data = request.POST.copy()
        data['assignment'] = assignment.id
        if request.FILES.get('submission_file'):
            data['submission_file'] = request.FILES['submission_file']
        serializer = AssignmentSubmissionSerializer(data=data)
        if serializer.is_valid():
            serializer.save(student=student, assignment=assignment)
            messages.success(request, 'Assignment submitted successfully!')
            return redirect('academics:assignment_detail', pk=assignment_id)
    else:
        serializer = AssignmentSubmissionSerializer()
    
    context = {
        'assignment': assignment,
        'form': serializer
    }
    return render(request, 'academics/assignment_submission.html', context)


@login_required
def grade_submission(request, submission_id):
    submission = get_object_or_404(StudentAssignment, id=submission_id)
    teacher = get_teacher_profile(request.user)
    if teacher is None and not is_admin_user(request.user):
        messages.error(request, 'Teacher or staff access is required to grade submissions.')
        return redirect('academics:assignment_detail', pk=submission.assignment_id)

    if request.method == 'POST':
        marks_obtained = request.POST.get('marks_obtained')
        feedback = request.POST.get('feedback', '')
        if marks_obtained not in (None, ''):
            submission.marks_obtained = marks_obtained
        submission.feedback = feedback
        if teacher is not None:
            submission.graded_by = teacher
        submission.graded_at = timezone.now()
        submission.save(update_fields=['marks_obtained', 'feedback', 'graded_by', 'graded_at'])
        messages.success(request, 'Submission graded successfully.')

    return redirect('academics:assignment_detail', pk=submission.assignment_id)


# Missing Views
@method_decorator(login_required, name='dispatch')
class ExamDeleteView(AcademicStaffRequiredMixin, DeleteView):
    model = Exam
    template_name = 'academics/exam_confirm_delete_modern.html'
    success_url = reverse_lazy('academics:exam_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Exam deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class AssignmentDeleteView(AcademicStaffRequiredMixin, DeleteView):
    model = Assignment
    template_name = 'academics/assignment_confirm_delete_modern.html'
    success_url = reverse_lazy('academics:assignment_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Assignment deleted successfully!')
        return super().delete(request, *args, **kwargs)


@method_decorator(login_required, name='dispatch')
class StudentAssignmentListView(InstitutionAccessMixin, ListView):
    model = StudentAssignment
    template_name = 'academics/student_assignment_list_modern.html'
    context_object_name = 'student_assignments'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = StudentAssignment.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'assignment__subject', 'assignment__class_obj'
        ).all()
        user = self.request.user
        if not is_platform_admin(user):
            if user.user_type == 'student':
                queryset = queryset.filter(student__user=user)
            elif user.user_type == 'parent':
                queryset = queryset.filter(student__parents__user=user)
            elif user.user_type == 'teacher':
                queryset = queryset.filter(assignment__teacher__user=user).distinct()
            else:
                institution_ids = user_institution_ids(user)
                queryset = queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()
        
        # Filter by search query
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(student__user__first_name__icontains=q) |
                Q(student__user__last_name__icontains=q) |
                Q(assignment__title__icontains=q)
            )
        
        return queryset.order_by('-submitted_at')


@method_decorator(login_required, name='dispatch')
class StudentAssignmentDetailView(DetailView):
    model = StudentAssignment
    template_name = 'academics/student_assignment_detail_modern.html'
    context_object_name = 'student_assignment'

    def get_queryset(self):
        queryset = StudentAssignment.objects.select_related(
            'student__user', 'student__current_class__academic_year__institution',
            'assignment__subject', 'assignment__class_obj'
        )
        user = self.request.user
        if is_platform_admin(user):
            return queryset
        if user.user_type == 'student':
            return queryset.filter(student__user=user)
        if user.user_type == 'parent':
            return queryset.filter(student__parents__user=user)
        if user.user_type == 'teacher':
            return queryset.filter(assignment__teacher__user=user).distinct()
        institution_ids = user_institution_ids(user)
        return queryset.filter(student__current_class__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()


@method_decorator(login_required, name='dispatch')
class StudentAssignmentCreateView(CreateView):
    model = StudentAssignment
    template_name = 'academics/student_assignment_form_modern.html'
    fields = ['assignment', 'submission_text', 'submission_file']
    success_url = reverse_lazy('academics:student_assignment_list')
    
    def form_valid(self, form):
        student = get_student_profile(self.request.user)
        if student is None:
            messages.error(self.request, 'Student profile required to submit assignments.')
            return self.form_invalid(form)
        form.instance.student = student
        messages.success(self.request, 'Assignment submitted successfully!')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class StudentAssignmentUpdateView(UpdateView):
    model = StudentAssignment
    template_name = 'academics/student_assignment_form_modern.html'
    fields = ['submission_text', 'submission_file']
    success_url = reverse_lazy('academics:student_assignment_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated successfully!')
        return super().form_valid(form)
