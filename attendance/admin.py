from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Attendance, ClassAttendance, TeacherAttendance, LeaveRequest


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'status', 'marked_by', 'created_at']
    list_filter = ['status', 'date', 'marked_by']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'student__user__email']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'date')
        }),
        ('Attendance Details', {
            'fields': ('status', 'remarks')
        }),
        ('System Information', {
            'fields': ('marked_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClassAttendance)
class ClassAttendanceAdmin(admin.ModelAdmin):
    list_display = ['class_obj', 'date', 'total_students', 'present_count', 'absent_count', 'attendance_percentage_display', 'marked_by']
    list_filter = ['class_obj', 'date', 'marked_by']
    search_fields = ['class_obj__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at', 'attendance_percentage_display']
    
    def attendance_percentage_display(self, obj):
        percentage = obj.attendance_percentage
        color = 'green' if percentage >= 90 else 'orange' if percentage >= 75 else 'red'
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percentage)
    attendance_percentage_display.short_description = 'Attendance %'
    
    fieldsets = (
        ('Class Information', {
            'fields': ('class_obj', 'date')
        }),
        ('Attendance Counts', {
            'fields': ('total_students', 'present_count', 'absent_count', 'late_count')
        }),
        ('System Information', {
            'fields': ('marked_by', 'attendance_percentage_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TeacherAttendance)
class TeacherAttendanceAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'date', 'status', 'check_in_time', 'check_out_time', 'created_at']
    list_filter = ['status', 'date']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'teacher__user__email']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Teacher Information', {
            'fields': ('teacher', 'date')
        }),
        ('Attendance Details', {
            'fields': ('status', 'check_in_time', 'check_out_time', 'remarks')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['get_user_name', 'leave_type', 'start_date', 'end_date', 'duration_days', 'status', 'approved_by', 'created_at']
    list_filter = ['leave_type', 'status', 'start_date', 'end_date']
    search_fields = ['student__user__first_name', 'student__user__last_name', 'teacher__user__first_name', 'teacher__user__last_name']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'duration_days_display']
    actions = ['approve_leaves', 'reject_leaves']
    
    def get_user_name(self, obj):
        if obj.student:
            return f"{obj.student.user.get_full_name()} (Student)"
        elif obj.teacher:
            return f"{obj.teacher.user.get_full_name()} (Teacher)"
        return "Unknown"
    get_user_name.short_description = 'User'
    
    def duration_days_display(self, obj):
        return f"{obj.duration_days} days"
    duration_days_display.short_description = 'Duration'
    
    def approve_leaves(self, request, queryset):
        from django.utils import timezone
        teacher = getattr(request.user, 'teacher_profile', None)
        if teacher is None:
            self.message_user(request, 'Only users with a teacher profile can approve leave requests.', level='error')
            return
        updated = queryset.update(
            status=LeaveRequest.LeaveStatus.APPROVED,
            approved_by=teacher,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} leave requests have been approved.')
    approve_leaves.short_description = "Approve selected leave requests"
    
    def reject_leaves(self, request, queryset):
        updated = queryset.update(status=LeaveRequest.LeaveStatus.REJECTED)
        self.message_user(request, f'{updated} leave requests have been rejected.')
    reject_leaves.short_description = "Reject selected leave requests"
    
    fieldsets = (
        ('Requestor Information', {
            'fields': ('student', 'teacher')
        }),
        ('Leave Details', {
            'fields': ('leave_type', 'start_date', 'end_date', 'duration_days_display', 'reason', 'supporting_document')
        }),
        ('Approval Information', {
            'fields': ('status', 'approved_by', 'approved_at', 'remarks')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Customize admin site
admin.site.site_header = "ADOM Institute - Attendance"
admin.site.site_title = "ADOM Institute Attendance"
admin.site.index_title = "Attendance Management"
