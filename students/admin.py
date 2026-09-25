from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AcademicYear, Class, Student, Parent


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_active', 'get_duration', 'get_class_count']
    list_filter = ['is_active', 'start_date', 'end_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
    )
    
    def get_duration(self, obj):
        return f"{(obj.end_date - obj.start_date).days} days"
    get_duration.short_description = 'Duration'
    
    def get_class_count(self, obj):
        return obj.classes.count()
    get_class_count.short_description = 'Classes'
    
    actions = ['activate_academic_year', 'deactivate_academic_year']
    
    def activate_academic_year(self, request, queryset):
        # Deactivate all other academic years first
        AcademicYear.objects.update(is_active=False)
        # Activate selected academic years
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} academic year(s) activated successfully.')
    activate_academic_year.short_description = "Activate selected academic years"
    
    def deactivate_academic_year(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} academic year(s) deactivated successfully.')
    deactivate_academic_year.short_description = "Deactivate selected academic years"


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'academic_year', 'section', 'capacity', 'get_student_count', 'is_active']
    list_filter = ['academic_year', 'is_active', 'section']
    search_fields = ['name', 'display_name', 'section']
    list_editable = ['is_active']
    ordering = ['academic_year', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'academic_year')
        }),
        ('Details', {
            'fields': ('section', 'capacity', 'is_active')
        }),
    )
    
    def get_student_count(self, obj):
        count = obj.students.count()
        return format_html('<span style="color: {};">{}</span>', 
                          'green' if count < obj.capacity else 'red', count)
    get_student_count.short_description = 'Students'
    
    actions = ['activate_classes', 'deactivate_classes']
    
    def activate_classes(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} class(es) activated successfully.')
    activate_classes.short_description = "Activate selected classes"
    
    def deactivate_classes(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} class(es) deactivated successfully.')
    deactivate_classes.short_description = "Deactivate selected classes"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'get_full_name', 'current_class', 'admission_status', 'gender', 'get_age', 'is_active', 'get_parent_count']
    list_filter = ['admission_status', 'gender', 'current_class', 'is_active', 'admission_date']
    search_fields = ['student_id', 'admission_number', 'roll_number', 'user__first_name', 'user__last_name', 'user__email']
    list_editable = ['admission_status', 'is_active']
    date_hierarchy = 'admission_date'
    ordering = ['-created_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'student_id', 'admission_number', 'roll_number')
        }),
        ('Personal Information', {
            'fields': ('gender', 'date_of_birth', 'phone_number', 'address')
        }),
        ('Academic Information', {
            'fields': ('current_class', 'admission_date', 'admission_status')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    def get_age(self, obj):
        from datetime import date
        today = date.today()
        age = today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return f"{age} years"
    get_age.short_description = 'Age'
    
    def get_parent_count(self, obj):
        return obj.parents.count()
    get_parent_count.short_description = 'Parents'
    
    actions = ['approve_admissions', 'reject_admissions', 'activate_students', 'deactivate_students']
    
    def approve_admissions(self, request, queryset):
        updated = queryset.update(admission_status='approved')
        self.message_user(request, f'{updated} student(s) admission approved successfully.')
    approve_admissions.short_description = "Approve selected admissions"
    
    def reject_admissions(self, request, queryset):
        updated = queryset.update(admission_status='rejected')
        self.message_user(request, f'{updated} student(s) admission rejected successfully.')
    reject_admissions.short_description = "Reject selected admissions"
    
    def activate_students(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} student(s) activated successfully.')
    activate_students.short_description = "Activate selected students"
    
    def deactivate_students(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} student(s) deactivated successfully.')
    deactivate_students.short_description = "Deactivate selected students"


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'student', 'relationship', 'occupation', 'phone_number', 'email', 'is_primary_contact', 'is_emergency_contact']
    list_filter = ['relationship', 'is_primary_contact', 'is_emergency_contact', 'created_at']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'phone_number', 'student__student_id', 'student__user__first_name']
    list_editable = ['is_primary_contact', 'is_emergency_contact']
    ordering = ['-created_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'student')
        }),
        ('Contact Information', {
            'fields': ('relationship', 'occupation', 'phone_number', 'email')
        }),
        ('Contact Preferences', {
            'fields': ('is_primary_contact', 'is_emergency_contact')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Full Name'
    get_full_name.admin_order_field = 'user__first_name'
    
    actions = ['set_primary_contact', 'set_emergency_contact']
    
    def set_primary_contact(self, request, queryset):
        # Remove primary contact from other parents of the same student
        for parent in queryset:
            Parent.objects.filter(student=parent.student, is_primary_contact=True).update(is_primary_contact=False)
        
        # Set selected parents as primary contact
        updated = queryset.update(is_primary_contact=True)
        self.message_user(request, f'{updated} parent(s) set as primary contact successfully.')
    set_primary_contact.short_description = "Set as primary contact"
    
    def set_emergency_contact(self, request, queryset):
        # Remove emergency contact from other parents of the same student
        for parent in queryset:
            Parent.objects.filter(student=parent.student, is_emergency_contact=True).update(is_emergency_contact=False)
        
        # Set selected parents as emergency contact
        updated = queryset.update(is_emergency_contact=True)
        self.message_user(request, f'{updated} parent(s) set as emergency contact successfully.')
    set_emergency_contact.short_description = "Set as emergency contact"
