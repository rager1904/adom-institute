from django.db import models
from django.utils.translation import gettext_lazy as _
from students.models import Student, Class, AcademicYear
from teachers.models import Teacher
from accounts.models import User
from accounts.validators import document_upload_validators


class AnalyticsEvent(models.Model):
    class EventType(models.TextChoices):
        LOGIN = 'login', _('Login')
        LOGOUT = 'logout', _('Logout')
        PAGE_VIEW = 'page_view', _('Page View')
        FEATURE_USE = 'feature_use', _('Feature Use')
        DATA_ACCESS = 'data_access', _('Data Access')
        REPORT_GENERATED = 'report_generated', _('Report Generated')
        PAYMENT_MADE = 'payment_made', _('Payment Made')
        ASSIGNMENT_SUBMITTED = 'assignment_submitted', _('Assignment Submitted')
        ATTENDANCE_MARKED = 'attendance_marked', _('Attendance Marked')
        MESSAGE_SENT = 'message_sent', _('Message Sent')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics_events')
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    event_data = models.JSONField(default=dict)
    
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_analytics_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'event_type', 'created_at'], name='analytics_event_user_idx'),
            models.Index(fields=['event_type', 'created_at'], name='analytics_event_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_event_type_display()} ({self.created_at})"


class StudentPerformance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='performance_records')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='student_performances')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='student_performances')
    
    # Academic metrics
    total_subjects = models.PositiveIntegerField(default=0)
    total_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    obtained_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade = models.CharField(max_length=10, blank=True, null=True)
    
    # Attendance metrics
    total_days = models.PositiveIntegerField(default=0)
    present_days = models.PositiveIntegerField(default=0)
    absent_days = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Assignment metrics
    total_assignments = models.PositiveIntegerField(default=0)
    submitted_assignments = models.PositiveIntegerField(default=0)
    assignment_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Fee metrics
    total_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee_payment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Calculated fields
    rank_in_class = models.PositiveIntegerField(blank=True, null=True)
    class_average = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_student_performance'
        unique_together = ('student', 'academic_year', 'class_obj')
        ordering = ['-percentage']
        constraints = [
            models.CheckConstraint(
                check=models.Q(obtained_marks__lte=models.F('total_marks')),
                name='analytics_st_marks_ck',
            ),
            models.CheckConstraint(
                check=models.Q(present_days__lte=models.F('total_days')),
                name='analytics_st_att_ck',
            ),
            models.CheckConstraint(
                check=models.Q(submitted_assignments__lte=models.F('total_assignments')),
                name='analytics_st_assign_ck',
            ),
            models.CheckConstraint(
                check=models.Q(paid_fees__lte=models.F('total_fees')),
                name='analytics_st_fees_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['academic_year', 'class_obj', 'percentage'], name='analytics_st_rank_idx'),
            models.Index(fields=['student', 'academic_year'], name='analytics_st_student_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.academic_year.name} ({self.percentage}%)"


class ClassPerformance(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_performances')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='class_performances')
    
    # Academic metrics
    total_students = models.PositiveIntegerField(default=0)
    average_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    highest_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    lowest_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Grade distribution
    grade_a_count = models.PositiveIntegerField(default=0)
    grade_b_count = models.PositiveIntegerField(default=0)
    grade_c_count = models.PositiveIntegerField(default=0)
    grade_d_count = models.PositiveIntegerField(default=0)
    grade_f_count = models.PositiveIntegerField(default=0)
    
    # Attendance metrics
    average_attendance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_attendance_days = models.PositiveIntegerField(default=0)
    
    # Fee collection metrics
    total_fees_expected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_fees_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fee_collection_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_class_performance'
        unique_together = ('class_obj', 'academic_year')
        ordering = ['-average_percentage']
        constraints = [
            models.CheckConstraint(
                check=models.Q(lowest_percentage__lte=models.F('highest_percentage')),
                name='analytics_class_range_ck',
            ),
            models.CheckConstraint(
                check=models.Q(total_fees_collected__lte=models.F('total_fees_expected')),
                name='analytics_class_fees_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['academic_year', 'average_percentage'], name='analytics_class_year_idx'),
        ]
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.academic_year.name} ({self.average_percentage}%)"


class TeacherPerformance(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='performance_records')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='teacher_performances')
    
    # Teaching metrics
    total_classes = models.PositiveIntegerField(default=0)
    total_students = models.PositiveIntegerField(default=0)
    total_subjects = models.PositiveIntegerField(default=0)
    
    # Attendance metrics
    total_teaching_days = models.PositiveIntegerField(default=0)
    present_days = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Assignment metrics
    assignments_created = models.PositiveIntegerField(default=0)
    assignments_graded = models.PositiveIntegerField(default=0)
    grading_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Student performance metrics
    average_student_performance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    student_satisfaction_score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    
    # Communication metrics
    messages_sent = models.PositiveIntegerField(default=0)
    announcements_published = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_teacher_performance'
        unique_together = ('teacher', 'academic_year')
        ordering = ['-average_student_performance']
        constraints = [
            models.CheckConstraint(
                check=models.Q(present_days__lte=models.F('total_teaching_days')),
                name='analytics_teacher_att_ck',
            ),
            models.CheckConstraint(
                check=models.Q(assignments_graded__lte=models.F('assignments_created')),
                name='analytics_teacher_assign_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['academic_year', 'average_student_performance'], name='analytics_teacher_year_idx'),
        ]
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.academic_year.name}"


class SchoolAnalytics(models.Model):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='school_analytics')
    
    # Student metrics
    total_students = models.PositiveIntegerField(default=0)
    new_admissions = models.PositiveIntegerField(default=0)
    transfers_in = models.PositiveIntegerField(default=0)
    transfers_out = models.PositiveIntegerField(default=0)
    dropouts = models.PositiveIntegerField(default=0)
    
    # Staff metrics
    total_teachers = models.PositiveIntegerField(default=0)
    total_administrators = models.PositiveIntegerField(default=0)
    total_support_staff = models.PositiveIntegerField(default=0)
    
    # Academic metrics
    total_classes = models.PositiveIntegerField(default=0)
    total_subjects = models.PositiveIntegerField(default=0)
    average_class_size = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Performance metrics
    overall_pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Financial metrics
    total_fees_expected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_fees_collected = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fee_collection_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    outstanding_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Infrastructure metrics
    total_rooms = models.PositiveIntegerField(default=0)
    room_utilization_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Technology metrics
    active_users = models.PositiveIntegerField(default=0)
    system_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_school_analytics'
        unique_together = ('academic_year',)
        ordering = ['-academic_year__start_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_fees_collected__lte=models.F('total_fees_expected')),
                name='analytics_school_fees_ck',
            ),
            models.CheckConstraint(
                check=models.Q(outstanding_fees__gte=0),
                name='analytics_school_out_ck',
            ),
        ]
    
    def __str__(self):
        return f"School Analytics - {self.academic_year.name}"


class Report(models.Model):
    class ReportType(models.TextChoices):
        STUDENT_PERFORMANCE = 'student_performance', _('Student Performance')
        CLASS_PERFORMANCE = 'class_performance', _('Class Performance')
        TEACHER_PERFORMANCE = 'teacher_performance', _('Teacher Performance')
        ATTENDANCE = 'attendance', _('Attendance')
        FEE_COLLECTION = 'fee_collection', _('Fee Collection')
        ACADEMIC_PROGRESS = 'academic_progress', _('Academic Progress')
        FINANCIAL = 'financial', _('Financial')
        CUSTOM = 'custom', _('Custom')
    
    class ReportFormat(models.TextChoices):
        PDF = 'pdf', _('PDF')
        EXCEL = 'excel', _('Excel')
        CSV = 'csv', _('CSV')
        JSON = 'json', _('JSON')
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    description = models.TextField(blank=True, null=True)
    
    # Report parameters
    parameters = models.JSONField(default=dict)
    filters = models.JSONField(default=dict)
    
    # Generated report
    file_path = models.FileField(
        upload_to='reports/',
        blank=True,
        null=True,
        validators=document_upload_validators,
    )
    file_size = models.PositiveIntegerField(blank=True, null=True)
    report_format = models.CharField(max_length=10, choices=ReportFormat.choices, default=ReportFormat.PDF)
    
    # Generation details
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    generated_at = models.DateTimeField(auto_now_add=True)
    generation_time = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    
    # Status
    is_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'analytics_report'
        ordering = ['-generated_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(generation_time__isnull=True) | models.Q(generation_time__gte=0),
                name='analytics_report_time_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['report_type', 'generated_at'], name='analytics_report_type_idx'),
            models.Index(fields=['generated_by', 'generated_at'], name='analytics_report_user_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"
