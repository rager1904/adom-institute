from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from students.models import Student, Class, AcademicYear
from teachers.models import Teacher, Subject
from accounts.validators import document_upload_validators


class ExamType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    weightage = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'academics_exam_type'
    
    def __str__(self):
        return self.name


class Exam(models.Model):
    name = models.CharField(max_length=200)
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE, related_name='exams')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='exams')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='exams')
    
    start_date = models.DateField()
    end_date = models.DateField()
    total_marks = models.PositiveIntegerField()
    passing_marks = models.PositiveIntegerField()
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'academics_exam'
        unique_together = ('name', 'academic_year', 'class_obj')
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='academics_exam_dates_ck',
            ),
            models.CheckConstraint(
                check=models.Q(passing_marks__lte=models.F('total_marks')),
                name='academics_exam_pass_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['academic_year', 'class_obj', 'is_active'], name='academics_exam_scope_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.class_obj.name} ({self.academic_year.name})"


class ExamSubject(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exam_subjects')
    max_marks = models.PositiveIntegerField()
    passing_marks = models.PositiveIntegerField()
    exam_date = models.DateField()
    duration = models.PositiveIntegerField(help_text='Duration in minutes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'academics_exam_subject'
        unique_together = ('exam', 'subject')
        constraints = [
            models.CheckConstraint(
                check=models.Q(passing_marks__lte=models.F('max_marks')),
                name='academics_exsub_pass_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['exam', 'subject', 'exam_date'], name='academics_exsub_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.exam.name} - {self.subject.name}"


class Grade(models.Model):
    name = models.CharField(max_length=10, unique=True)
    min_marks = models.PositiveIntegerField()
    max_marks = models.PositiveIntegerField()
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)
    description = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'academics_grade'
        ordering = ['min_marks']
    
    def __str__(self):
        return f"{self.name} ({self.min_marks}-{self.max_marks})"


class StudentExamResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_results')
    exam_subject = models.ForeignKey(ExamSubject, on_delete=models.CASCADE, related_name='student_results')
    
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    
    created_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='created_results')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'academics_student_exam_result'
        unique_together = ('student', 'exam_subject')
        constraints = [
            models.CheckConstraint(
                check=models.Q(marks_obtained__gte=0),
                name='academics_result_marks_ck',
            ),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.exam_subject.subject.name}"
    
    @property
    def percentage(self):
        if self.exam_subject.max_marks > 0:
            return (self.marks_obtained / self.exam_subject.max_marks) * 100
        return 0
    
    @property
    def is_pass(self):
        return self.marks_obtained >= self.exam_subject.passing_marks


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='assignments')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='created_assignments')
    
    due_date = models.DateTimeField()
    max_marks = models.PositiveIntegerField()
    attachment = models.FileField(
        upload_to='assignments/',
        blank=True,
        null=True,
        validators=document_upload_validators,
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'academics_assignment'
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_marks__gt=0),
                name='academics_assign_marks_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['class_obj', 'due_date'], name='academics_assign_due_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.subject.name}"


class StudentAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='submitted_assignments')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='student_submissions')
    
    submission_file = models.FileField(
        upload_to='assignment_submissions/',
        validators=document_upload_validators,
    )
    submission_text = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    graded_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='graded_assignments')
    graded_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'academics_student_assignment'
        unique_together = ('student', 'assignment')
        constraints = [
            models.CheckConstraint(
                check=models.Q(marks_obtained__isnull=True) | models.Q(marks_obtained__gte=0),
                name='academics_submission_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['student', 'assignment'], name='academics_sub_student_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assignment.title}"
    
    @property
    def is_late(self):
        return self.submitted_at > self.assignment.due_date
    
    @property
    def is_graded(self):
        return self.marks_obtained is not None
