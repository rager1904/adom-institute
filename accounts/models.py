from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from .validators import image_upload_validators


class Institution(models.Model):
    """
    Tenant boundary for schools, colleges, universities, and education groups.
    """
    class InstitutionType(models.TextChoices):
        UNIVERSITY = 'university', _('University')
        COLLEGE = 'college', _('College')
        SECONDARY_SCHOOL = 'secondary_school', _('Secondary School')
        PRIMARY_SCHOOL = 'primary_school', _('Primary School')
        TRAINING_CENTER = 'training_center', _('Training Center')
        OTHER = 'other', _('Other')

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    institution_type = models.CharField(
        max_length=30,
        choices=InstitutionType.choices,
        default=InstitutionType.SECONDARY_SCHOOL,
    )
    country = models.CharField(max_length=100, default='Zambia')
    province = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_institution'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'super_admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    """
    Custom User model with role-based access control
    """
    class UserType(models.TextChoices):
        SUPER_ADMIN = 'super_admin', _('Super Admin')
        ADMINISTRATOR = 'administrator', _('Administrator')
        TEACHER = 'teacher', _('Teacher')
        STUDENT = 'student', _('Student')
        PARENT = 'parent', _('Parent/Guardian')
        ACCOUNTANT = 'accountant', _('Accountant')

    # Remove username field and use email as primary identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # User type and role
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.STUDENT
    )
    
    # Profile information
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        validators=image_upload_validators,
    )
    
    # Two-factor authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    
    # Account status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    # Required fields for Django
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'user_type']
    
    # Use custom UserManager
    objects = UserManager()
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        db_table = 'auth_user'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name
    
    @property
    def is_super_admin(self):
        return self.user_type == self.UserType.SUPER_ADMIN
    
    @property
    def is_administrator(self):
        return self.user_type == self.UserType.ADMINISTRATOR
    
    @property
    def is_teacher(self):
        return self.user_type == self.UserType.TEACHER
    
    @property
    def is_student(self):
        return self.user_type == self.UserType.STUDENT
    
    @property
    def is_parent(self):
        return self.user_type == self.UserType.PARENT
    
    @property
    def is_accountant(self):
        return self.user_type == self.UserType.ACCOUNTANT
    
    def has_role(self, *roles):
        """Check if user has any of the specified roles"""
        return self.user_type in roles


class UserProfile(models.Model):
    """
    Extended profile information for users
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Additional personal information
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, null=True)
    
    # Preferences
    language_preference = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    notification_preferences = models.JSONField(default=dict)
    
    # Additional fields for different user types
    bio = models.TextField(blank=True, null=True)
    skills = models.JSONField(default=list)
    certifications = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_user_profile'
    
    def __str__(self):
        return f"Profile for {self.user.get_full_name()}"


class Permission(models.Model):
    """
    Custom permissions for role-based access control
    """
    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'accounts_permission'
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
    
    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Roles with associated permissions
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts_role'
    
    def __str__(self):
        return self.name


class UserRole(models.Model):
    """
    Many-to-many relationship between users and roles
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='role_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'accounts_user_role'
        unique_together = ('user', 'role')
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.name}"


class InstitutionMembership(models.Model):
    """
    Connects users to the institutions they may access.
    """
    class MembershipRole(models.TextChoices):
        OWNER = 'owner', _('Owner')
        ADMINISTRATOR = 'administrator', _('Administrator')
        TEACHER = 'teacher', _('Teacher')
        STUDENT = 'student', _('Student')
        PARENT = 'parent', _('Parent/Guardian')
        ACCOUNTANT = 'accountant', _('Accountant')
        VIEWER = 'viewer', _('Viewer')

    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='institution_memberships')
    role = models.CharField(max_length=30, choices=MembershipRole.choices)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_institution_memberships',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_institution_membership'
        unique_together = ('institution', 'user')
        indexes = [
            models.Index(fields=['institution', 'role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.institution.name} ({self.role})"


class AuditLog(models.Model):
    """
    Audit trail for user actions
    """
    class ActionType(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        LOGIN = 'login', _('Login')
        LOGOUT = 'logout', _('Logout')
        PASSWORD_CHANGE = 'password_change', _('Password Change')
        ROLE_ASSIGNMENT = 'role_assignment', _('Role Assignment')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ActionType.choices)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'accounts_audit_log'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.action} - {self.timestamp}"
