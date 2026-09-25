from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Teacher, Subject, TeacherSubject, Department, TeacherDepartment


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'get_teacher_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_teacher_count(self, obj):
        return obj.teacher_subjects.count()
    get_teacher_count.short_description = 'Teachers'
    get_teacher_count.admin_order_field = 'teacher_subjects__count'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'head_of_department', 'is_active', 'get_teacher_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description')
        }),
        ('Leadership', {
            'fields': ('head_of_department',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_teacher_count(self, obj):
        return obj.teacher_departments.count()
    get_teacher_count.short_description = 'Teachers'
    get_teacher_count.admin_order_field = 'teacher_departments__count'


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = [
        'employee_id', 'get_full_name', 'get_email', 'employment_type', 
        'employment_status', 'qualification', 'experience_years', 
        'get_subject_count', 'get_department_count', 'is_class_teacher'
    ]
    list_filter = [
        'employment_type', 'employment_status', 'is_class_teacher', 
        'is_head_of_department', 'joining_date', 'created_at'
    ]
    search_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 
        'user__email', 'qualification', 'specialization'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['user__first_name', 'user__last_name']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id')
        }),
        ('Employment Details', {
            'fields': (
                'employment_type', 'employment_status', 'joining_date', 
                'contract_end_date'
            )
        }),
        ('Professional Information', {
            'fields': ('qualification', 'specialization', 'experience_years')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'emergency_contact', 'address')
        }),
        ('Roles', {
            'fields': ('is_class_teacher', 'is_head_of_department')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'
    
    def get_subject_count(self, obj):
        return obj.teacher_subjects.count()
    get_subject_count.short_description = 'Subjects'
    
    def get_department_count(self, obj):
        return obj.teacher_departments.count()
    get_department_count.short_description = 'Departments'
    
    actions = ['activate_teachers', 'deactivate_teachers', 'set_full_time', 'set_part_time']
    
    def activate_teachers(self, request, queryset):
        updated = queryset.update(employment_status=Teacher.EmploymentStatus.ACTIVE)
        self.message_user(request, f'{updated} teachers have been activated.')
    activate_teachers.short_description = "Activate selected teachers"
    
    def deactivate_teachers(self, request, queryset):
        updated = queryset.update(employment_status=Teacher.EmploymentStatus.INACTIVE)
        self.message_user(request, f'{updated} teachers have been deactivated.')
    deactivate_teachers.short_description = "Deactivate selected teachers"
    
    def set_full_time(self, request, queryset):
        updated = queryset.update(employment_type=Teacher.EmploymentType.FULL_TIME)
        self.message_user(request, f'{updated} teachers have been set to full-time.')
    set_full_time.short_description = "Set selected teachers to full-time"
    
    def set_part_time(self, request, queryset):
        updated = queryset.update(employment_type=Teacher.EmploymentType.PART_TIME)
        self.message_user(request, f'{updated} teachers have been set to part-time.')
    set_part_time.short_description = "Set selected teachers to part-time"


@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'subject__name']
    readonly_fields = ['created_at']
    ordering = ['teacher__user__first_name', 'subject__name']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('teacher', 'subject', 'is_primary')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['set_primary_subjects', 'remove_primary_subjects']
    
    def set_primary_subjects(self, request, queryset):
        updated = queryset.update(is_primary=True)
        self.message_user(request, f'{updated} subject assignments have been set as primary.')
    set_primary_subjects.short_description = "Set selected assignments as primary"
    
    def remove_primary_subjects(self, request, queryset):
        updated = queryset.update(is_primary=False)
        self.message_user(request, f'{updated} subject assignments have been removed as primary.')
    remove_primary_subjects.short_description = "Remove primary status from selected assignments"


@admin.register(TeacherDepartment)
class TeacherDepartmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'department', 'created_at']
    list_filter = ['created_at', 'department']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'department__name']
    readonly_fields = ['created_at']
    ordering = ['teacher__user__first_name', 'department__name']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('teacher', 'department')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
