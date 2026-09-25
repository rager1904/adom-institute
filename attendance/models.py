from django.db import models
from django.utils.translation import gettext_lazy as _
from students.models import Student, Class
from teachers.models import Teacher
from accounts.validators import document_upload_validators


class Attendance(models.Model):
    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', _('Present')
        ABSENT = 'absent', _('Absent')
        LATE = 'late', _('Late')
        HALF_DAY = 'half_day', _('Half Day')
        EXCUSED = 'excused', _('Excused')
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT)
    remarks = models.TextField(blank=True, null=True)
    
    marked_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_attendance'
        unique_together = ('student', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['student', 'date', 'status'], name='att_student_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.date} ({self.get_status_display()})"


class ClassAttendance(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_attendances')
    date = models.DateField()
    total_students = models.PositiveIntegerField()
    present_count = models.PositiveIntegerField(default=0)
    absent_count = models.PositiveIntegerField(default=0)
    late_count = models.PositiveIntegerField(default=0)
    
    marked_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='marked_class_attendances')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_class_attendance'
        unique_together = ('class_obj', 'date')
        ordering = ['-date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(present_count__lte=models.F('total_students')),
                name='att_class_present_ck',
            ),
            models.CheckConstraint(
                check=models.Q(absent_count__lte=models.F('total_students')),
                name='att_class_absent_ck',
            ),
            models.CheckConstraint(
                check=models.Q(late_count__lte=models.F('total_students')),
                name='att_class_late_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['class_obj', 'date'], name='att_class_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.date} ({self.present_count}/{self.total_students})"
    
    @property
    def attendance_percentage(self):
        if self.total_students > 0:
            return (self.present_count / self.total_students) * 100
        return 0


class TeacherAttendance(models.Model):
    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', _('Present')
        ABSENT = 'absent', _('Absent')
        LATE = 'late', _('Late')
        HALF_DAY = 'half_day', _('Half Day')
        ON_LEAVE = 'on_leave', _('On Leave')
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teacher_attendances')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT)
    check_in_time = models.TimeField(blank=True, null=True)
    check_out_time = models.TimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_teacher_attendance'
        unique_together = ('teacher', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['teacher', 'date', 'status'], name='att_teacher_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.date} ({self.get_status_display()})"


class LeaveRequest(models.Model):
    class LeaveType(models.TextChoices):
        SICK_LEAVE = 'sick_leave', _('Sick Leave')
        CASUAL_LEAVE = 'casual_leave', _('Casual Leave')
        ANNUAL_LEAVE = 'annual_leave', _('Annual Leave')
        MATERNITY_LEAVE = 'maternity_leave', _('Maternity Leave')
        PATERNITY_LEAVE = 'paternity_leave', _('Paternity Leave')
        OTHER = 'other', _('Other')
    
    class LeaveStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='leave_requests', null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='leave_requests', null=True, blank=True)
    
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    supporting_document = models.FileField(
        upload_to='leave_documents/',
        blank=True,
        null=True,
        validators=document_upload_validators,
    )
    
    status = models.CharField(max_length=20, choices=LeaveStatus.choices, default=LeaveStatus.PENDING)
    approved_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    approved_at = models.DateTimeField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_leave_request'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='att_leave_dates_ck',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(student__isnull=False, teacher__isnull=True)
                    | models.Q(student__isnull=True, teacher__isnull=False)
                ),
                name='att_leave_one_owner_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'start_date'], name='att_leave_status_idx'),
        ]
    
    def __str__(self):
        user = self.student.user if self.student else self.teacher.user
        return f"{user.get_full_name()} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
    
    @property
    def is_approved(self):
        return self.status == self.LeaveStatus.APPROVED
    
    @property
    def is_pending(self):
        return self.status == self.LeaveStatus.PENDING
