from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from accounts.models import Institution, User


class AcademicYear(models.Model):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name='academic_years',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'students_academic_year'
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='students_year_dates_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['institution', 'is_active'], name='students_year_inst_idx'),
        ]
    
    def __str__(self):
        return self.name


class Class(models.Model):
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classes')
    capacity = models.PositiveIntegerField(default=30)
    section = models.CharField(max_length=10, blank=True, null=True)
  
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'students_class'
        verbose_name_plural = 'classes'
        constraints = [
            models.CheckConstraint(
                check=models.Q(capacity__gt=0),
                name='students_class_cap_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['academic_year', 'is_active'], name='students_class_year_idx'),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.academic_year.name})"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', _('Male')
        FEMALE = 'female', _('Female')
        OTHER = 'other', _('Other')
    
    class AdmissionStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    admission_number = models.CharField(max_length=20, unique=True)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField()
    
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='students')
    admission_date = models.DateField()
    admission_status = models.CharField(max_length=20, choices=AdmissionStatus.choices, default=AdmissionStatus.PENDING)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'students_student'
        constraints = [
            models.CheckConstraint(
                check=models.Q(admission_date__gte=models.F('date_of_birth')),
                name='students_admission_age_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['current_class', 'is_active'], name='students_class_active_idx'),
            models.Index(fields=['admission_status', 'is_active'], name='students_adm_status_idx'),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    @property
    def age(self):
        today = timezone.localdate()
        years = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            years -= 1
        return years


class Parent(models.Model):
    class Relationship(models.TextChoices):
        FATHER = 'father', _('Father')
        MOTHER = 'mother', _('Mother')
        GUARDIAN = 'guardian', _('Guardian')
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    
    relationship = models.CharField(max_length=20, choices=Relationship.choices)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField()
    
    is_primary_contact = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'students_parent'
        indexes = [
            models.Index(fields=['student', 'is_primary_contact'], name='students_parent_primary_idx'),
            models.Index(fields=['student', 'is_emergency_contact'], name='students_parent_emerg_idx'),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.relationship})"
