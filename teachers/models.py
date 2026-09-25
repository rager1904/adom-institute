from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import User


class Teacher(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', _('Full Time')
        PART_TIME = 'part_time', _('Part Time')
        CONTRACT = 'contract', _('Contract')
        VISITING = 'visiting', _('Visiting')
    
    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        ON_LEAVE = 'on_leave', _('On Leave')
        TERMINATED = 'terminated', _('Terminated')
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    
    # Employment details
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    employment_status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)
    joining_date = models.DateField()
    contract_end_date = models.DateField(blank=True, null=True)
    
    # Professional information
    qualification = models.CharField(max_length=100)
    specialization = models.CharField(max_length=100, blank=True, null=True)
    experience_years = models.PositiveIntegerField(default=0)
    
    # Contact information
    phone_number = models.CharField(max_length=15)
    emergency_contact = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField()
    
    # Additional information
    is_class_teacher = models.BooleanField(default=False)
    is_head_of_department = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teachers_teacher'
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teachers_subject'
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class TeacherSubject(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teacher_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='teacher_subjects')
    is_primary = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'teachers_teacher_subject'
        unique_together = ('teacher', 'subject')
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.subject.name}"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    head_of_department = models.ForeignKey(
        Teacher, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='headed_departments'
    )
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teachers_department'
    
    def __str__(self):
        return self.name


class TeacherDepartment(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teacher_departments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='teacher_departments')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'teachers_teacher_department'
        unique_together = ('teacher', 'department')
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.department.name}"
