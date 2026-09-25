from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.permissions import is_platform_admin, user_institution_ids
from academics.models import Assignment, Exam, StudentAssignment, StudentExamResult
from analytics.models import AnalyticsEvent
from attendance.models import Attendance
from communication.models import Notification
from adom_institute.agents import list_agent_definitions
from adom_institute.registry import get_ai_runtime_config
from fees.models import Payment, StudentFee
from students.models import Class, Student
from teachers.models import Teacher


def build_dashboard_context(user):
    if user.is_student:
        role_context = _student_context(user)
    elif user.is_teacher:
        role_context = _teacher_context(user)
    elif user.is_parent:
        role_context = _parent_context(user)
    else:
        role_context = _admin_context(user)

    role_context['ai'] = _ai_context()
    role_context['notifications'] = _notification_context(user)
    return role_context


def _student_context(user):
    student = getattr(user, 'student_profile', None)
    if not student:
        return _empty_role_context('Student', 'Complete your student profile to activate academic insights.')

    now = timezone.now()
    class_obj = student.current_class
    assignment_queryset = Assignment.objects.filter(class_obj=class_obj, is_active=True) if class_obj else Assignment.objects.none()
    submitted_assignment_ids = StudentAssignment.objects.filter(student=student).values('assignment_id')
    pending_assignments = assignment_queryset.exclude(id__in=submitted_assignment_ids).filter(due_date__gte=now).order_by('due_date')
    attendance_counts = Attendance.objects.filter(student=student).aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status=Attendance.AttendanceStatus.PRESENT)),
        absent=Count('id', filter=Q(status=Attendance.AttendanceStatus.ABSENT)),
        late=Count('id', filter=Q(status=Attendance.AttendanceStatus.LATE)),
    )
    total_attendance = attendance_counts['total'] or 0
    present_attendance = attendance_counts['present'] or 0
    attendance_rate = round((present_attendance / total_attendance) * 100, 1) if total_attendance else 0
    average_percentage = StudentExamResult.objects.filter(student=student).annotate(
        percentage=_exam_percentage_expression()
    ).aggregate(value=Avg('percentage'))['value'] or 0
    upcoming_exams = Exam.objects.filter(class_obj=class_obj, is_active=True, start_date__gte=now.date()).order_by('start_date')[:3] if class_obj else []
    completed_assignments = StudentAssignment.objects.filter(student=student).count()
    total_assignments = assignment_queryset.count()
    progress = round((completed_assignments / total_assignments) * 100, 1) if total_assignments else 0

    return {
        'role_label': 'Student',
        'headline': 'Academic command center',
        'subheadline': 'Track grades, attendance, deadlines, and AI-guided study priorities.',
        'primary_profile': student,
        'stats': [
            _stat('GPA Overview', _format_gpa(average_percentage), 'fa-chart-line', 'Estimated from graded results'),
            _stat('Attendance', f'{attendance_rate}%', 'fa-calendar-check', f'{present_attendance}/{total_attendance} present'),
            _stat('Course Progress', f'{progress}%', 'fa-route', f'{completed_assignments}/{total_assignments} assignments submitted'),
            _stat('Upcoming Exams', len(upcoming_exams), 'fa-file-pen', 'Next scheduled assessments'),
        ],
        'focus_items': [
            _focus('Assignment Deadlines', assignment.title, assignment.due_date, 'fa-clipboard-list')
            for assignment in pending_assignments[:4]
        ],
        'secondary_items': [
            _focus('Upcoming Exam', exam.name, exam.start_date, 'fa-file-circle-check')
            for exam in upcoming_exams
        ],
        'recommendations': _student_recommendations(attendance_rate, average_percentage, pending_assignments.count()),
        'quick_actions': [
            _action('Student Portal', 'students:student_portal', 'fa-user-graduate'),
            _action('My Academics', 'academics:my_academics', 'fa-book-open'),
            _action('My Attendance', 'attendance:my_attendance', 'fa-calendar-check'),
            _action('My Fees', 'fees:my_fees', 'fa-credit-card'),
            _action('Library', 'library:dashboard', 'fa-book-open'),
            _action('Messages', 'communication:inbox', 'fa-comments'),
        ],
    }


def _teacher_context(user):
    teacher = getattr(user, 'teacher_profile', None)
    if not teacher:
        return _empty_role_context('Teacher', 'Complete your teacher profile to activate course analytics.')

    assignments = Assignment.objects.filter(teacher=teacher)
    class_ids = assignments.values_list('class_obj_id', flat=True).distinct()
    student_count = Student.objects.filter(current_class_id__in=class_ids, is_active=True).count()
    ungraded_count = StudentAssignment.objects.filter(assignment__teacher=teacher, marks_obtained__isnull=True).count()
    average_score = StudentExamResult.objects.filter(created_by=teacher).annotate(
        percentage=_exam_percentage_expression()
    ).aggregate(value=Avg('percentage'))['value'] or 0
    recent_assignments = assignments.select_related('class_obj', 'subject').order_by('-created_at')[:4]

    return {
        'role_label': 'Teacher',
        'headline': 'Teaching operations dashboard',
        'subheadline': 'Manage assessments, grading workload, attendance, and class performance.',
        'primary_profile': teacher,
        'stats': [
            _stat('Active Courses', len(set(class_ids)), 'fa-chalkboard', 'Classes with assigned work'),
            _stat('Students Reached', student_count, 'fa-user-graduate', 'Across active classes'),
            _stat('Ungraded Work', ungraded_count, 'fa-clipboard-question', 'Submissions needing review'),
            _stat('Avg Assessment Score', f'{round(average_score, 1)}%', 'fa-chart-line', 'Results you recorded'),
        ],
        'focus_items': [
            _focus('Assessment', assignment.title, assignment.due_date, 'fa-clipboard-list')
            for assignment in recent_assignments
        ],
        'secondary_items': [
            _focus('Class Analytics', 'Review low-performing cohorts', None, 'fa-chart-pie'),
            _focus('Attendance', 'Mark or audit daily attendance', None, 'fa-calendar-check'),
        ],
        'recommendations': [
            'Prioritize ungraded submissions before creating new assessments.',
            'Use item analysis after each exam to identify weak topics.',
            'Send targeted resources to students below class average.',
        ],
        'quick_actions': [
            _action('Courses', 'academics:course_list', 'fa-layer-group'),
            _action('Create Assignment', 'academics:assignment_create', 'fa-plus'),
            _action('Grade Submissions', 'academics:student_assignment_list', 'fa-pen-to-square'),
            _action('Attendance', 'attendance:bulk_attendance', 'fa-calendar-check'),
            _action('Analytics', 'analytics:dashboard', 'fa-chart-bar'),
        ],
    }


def _parent_context(user):
    parent = getattr(user, 'parent_profile', None)
    student = parent.student if parent else None
    if not student:
        return _empty_role_context('Parent', 'Link a child profile to activate guardian insights.')

    outstanding = StudentFee.objects.filter(student=student).aggregate(
        total=Sum(F('amount') - F('paid_amount'))
    )['total'] or Decimal('0')
    attendance_total = Attendance.objects.filter(student=student).count()
    missed_days = Attendance.objects.filter(student=student, status=Attendance.AttendanceStatus.ABSENT).count()
    pending_assignments = Assignment.objects.filter(
        class_obj=student.current_class,
        is_active=True,
        due_date__gte=timezone.now(),
    ).exclude(id__in=StudentAssignment.objects.filter(student=student).values('assignment_id')).count()

    return {
        'role_label': 'Parent',
        'headline': 'Guardian overview',
        'subheadline': 'Monitor academic progress, attendance, communications, and fees.',
        'primary_profile': parent,
        'stats': [
            _stat('Child', student.user.get_full_name(), 'fa-user-graduate', student.student_id),
            _stat('Missed Days', missed_days, 'fa-calendar-xmark', f'{attendance_total} attendance records'),
            _stat('Pending Work', pending_assignments, 'fa-clipboard-list', 'Open assignment deadlines'),
            _stat('Outstanding Fees', f'K {outstanding}', 'fa-credit-card', 'Current balance'),
        ],
        'focus_items': [
            _focus('Student Profile', student.user.get_full_name(), None, 'fa-user-graduate'),
            _focus('Fee Follow-up', f'Outstanding balance: K {outstanding}', None, 'fa-credit-card'),
        ],
        'secondary_items': [],
        'recommendations': [
            'Review attendance weekly and contact the class teacher after repeated absences.',
            'Check assignment deadlines every Monday with your child.',
            'Keep fee commitments visible to avoid overdue balances.',
        ],
        'quick_actions': [
            _action('Courses', 'academics:course_list', 'fa-layer-group'),
            _action('Child Profile', 'students:student_detail', 'fa-user-graduate', args=[student.pk]),
            _action('My Academics', 'academics:my_academics', 'fa-book-open'),
            _action('My Attendance', 'attendance:my_attendance', 'fa-calendar-check'),
            _action('My Fees', 'fees:my_fees', 'fa-credit-card'),
            _action('Messages', 'communication:inbox', 'fa-comments'),
        ],
    }


def _admin_context(user):
    institution_ids = user_institution_ids(user)
    student_queryset = Student.objects.all()
    teacher_queryset = Teacher.objects.all()
    class_queryset = Class.objects.all()
    if institution_ids and not is_platform_admin(user):
        student_queryset = student_queryset.filter(current_class__academic_year__institution_id__in=institution_ids)
        class_queryset = class_queryset.filter(academic_year__institution_id__in=institution_ids)

    revenue = Payment.objects.filter(payment_status=Payment.PaymentStatus.COMPLETED)
    if institution_ids and not is_platform_admin(user):
        revenue = revenue.filter(student__current_class__academic_year__institution_id__in=institution_ids)
    revenue_total = revenue.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    active_users_24h = AnalyticsEvent.objects.filter(created_at__gte=timezone.now() - timedelta(days=1)).values('user').distinct().count()

    return {
        'role_label': 'Administrator',
        'headline': 'Institution operations dashboard',
        'subheadline': 'Track institution health, students, revenue, user activity, and AI readiness.',
        'primary_profile': user,
        'stats': [
            _stat('Students', student_queryset.filter(is_active=True).count(), 'fa-user-graduate', 'Active learners'),
            _stat('Teachers', teacher_queryset.filter(employment_status=Teacher.EmploymentStatus.ACTIVE).count(), 'fa-chalkboard-teacher', 'Active teaching staff'),
            _stat('Classes', class_queryset.filter(is_active=True).count(), 'fa-school', 'Active class groups'),
            _stat('Revenue', f'K {revenue_total}', 'fa-money-bill-trend-up', 'Completed payments'),
            _stat('24h Active Users', active_users_24h, 'fa-heart-pulse', 'System health signal'),
        ],
        'focus_items': [
            _focus('User Management', 'Review roles and institution memberships', None, 'fa-users-gear'),
            _focus('Revenue Analytics', 'Audit outstanding balances and collections', None, 'fa-chart-line'),
            _focus('System Health', 'Monitor activity, logs, and background jobs', None, 'fa-server'),
        ],
        'secondary_items': [],
        'recommendations': [
            'Prioritize institution-level role audits before national deployment.',
            'Move production reporting workloads to async Celery jobs.',
            'Enable the open-source ADOM Institute AI stack only after RAG permissions are enforced.',
        ],
        'quick_actions': [
            _action('Courses', 'academics:course_list', 'fa-layer-group'),
            _action('Students', 'students:student_list', 'fa-user-graduate'),
            _action('Teachers', 'teachers:teacher_list', 'fa-chalkboard-teacher'),
            _action('Fees', 'fees:dashboard', 'fa-credit-card'),
            _action('Analytics', 'analytics:dashboard', 'fa-chart-bar'),
        ],
    }


def _ai_context():
    runtime = get_ai_runtime_config()
    agent_names = [agent.name for agent in list_agent_definitions()]
    return {
        'enabled': runtime['enabled'],
        'provider': runtime['provider'],
        'chat_model': runtime['default_chat_model'],
        'embedding_model': runtime['default_embedding_model'],
        'vector_store': runtime['vector_store'],
        'agents': agent_names[:6],
        'agent_count': len(agent_names),
    }


def _notification_context(user):
    return {
        'unread': Notification.objects.filter(recipient=user).exclude(status=Notification.NotificationStatus.READ).count(),
        'urgent': Notification.objects.filter(recipient=user, is_urgent=True).exclude(status=Notification.NotificationStatus.READ).count(),
    }


def _empty_role_context(role_label, message):
    return {
        'role_label': role_label,
        'headline': f'{role_label} dashboard',
        'subheadline': message,
        'primary_profile': None,
        'stats': [],
        'focus_items': [],
        'secondary_items': [],
        'recommendations': [message],
        'quick_actions': [_action('Profile Settings', 'accounts:profile', 'fa-user-gear')],
    }


def _format_gpa(percentage):
    if percentage >= 86:
        return '4.0'
    if percentage >= 75:
        return '3.5'
    if percentage >= 65:
        return '3.0'
    if percentage >= 50:
        return '2.0'
    if percentage:
        return '1.0'
    return 'N/A'


def _exam_percentage_expression():
    return ExpressionWrapper(
        F('marks_obtained') * Value(
            Decimal('100.00'),
            output_field=DecimalField(max_digits=5, decimal_places=2),
        ) / F('exam_subject__max_marks'),
        output_field=DecimalField(max_digits=6, decimal_places=2),
    )


def _student_recommendations(attendance_rate, average_percentage, pending_count):
    recommendations = []
    if attendance_rate and attendance_rate < 85:
        recommendations.append('Attendance is below target; schedule make-up study time for missed lessons.')
    if average_percentage and average_percentage < 60:
        recommendations.append('Focus this week on weaker exam topics and request teacher feedback.')
    if pending_count:
        recommendations.append(f'Complete {pending_count} pending assignment(s) before starting new study topics.')
    if not recommendations:
        recommendations.append('Maintain your current pace and use past papers for spaced exam practice.')
    return recommendations


def _stat(label, value, icon, detail):
    return {'label': label, 'value': value, 'icon': icon, 'detail': detail}


def _focus(category, title, due_at, icon):
    return {'category': category, 'title': title, 'due_at': due_at, 'icon': icon}


def _action(label, url_name, icon, args=None):
    try:
        url = reverse(url_name, args=args or [])
    except NoReverseMatch:
        url = '#'
    return {'label': label, 'url': url, 'icon': icon}
