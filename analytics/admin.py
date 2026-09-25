from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    AnalyticsEvent, StudentPerformance, ClassPerformance, 
    TeacherPerformance, SchoolAnalytics, Report
)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'ip_address', 'created_at']
    list_filter = ['event_type', 'created_at', 'user__user_type']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'ip_address']
    readonly_fields = ['created_at', 'session_id']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('user', 'event_type', 'event_data')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'session_id', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentPerformance)
class StudentPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'academic_year', 'class_obj', 'percentage', 
        'attendance_percentage', 'rank_in_class', 'grade'
    ]
    list_filter = [
        'academic_year', 'class_obj', 'grade', 'created_at'
    ]
    search_fields = [
        'student__user__username', 'student__user__first_name', 
        'student__user__last_name', 'student__student_id'
    ]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'academic_year', 'class_obj')
        }),
        ('Academic Performance', {
            'fields': (
                'total_subjects', 'total_marks', 'obtained_marks', 
                'percentage', 'grade', 'rank_in_class', 'class_average'
            )
        }),
        ('Attendance', {
            'fields': (
                'total_days', 'present_days', 'absent_days', 'attendance_percentage'
            )
        }),
        ('Assignments', {
            'fields': (
                'total_assignments', 'submitted_assignments', 'assignment_completion_rate'
            )
        }),
        ('Fees', {
            'fields': ('total_fees', 'paid_fees', 'fee_payment_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student__user', 'academic_year', 'class_obj'
        )


@admin.register(ClassPerformance)
class ClassPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'class_obj', 'academic_year', 'total_students', 'average_percentage',
        'average_attendance', 'fee_collection_rate'
    ]
    list_filter = ['academic_year', 'class_obj', 'created_at']
    search_fields = ['class_obj__name', 'class_obj__display_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Class Information', {
            'fields': ('class_obj', 'academic_year')
        }),
        ('Student Metrics', {
            'fields': ('total_students',)
        }),
        ('Academic Performance', {
            'fields': (
                'average_percentage', 'highest_percentage', 'lowest_percentage'
            )
        }),
        ('Grade Distribution', {
            'fields': (
                'grade_a_count', 'grade_b_count', 'grade_c_count', 
                'grade_d_count', 'grade_f_count'
            )
        }),
        ('Attendance', {
            'fields': ('average_attendance', 'total_attendance_days')
        }),
        ('Fee Collection', {
            'fields': (
                'total_fees_expected', 'total_fees_collected', 'fee_collection_rate'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TeacherPerformance)
class TeacherPerformanceAdmin(admin.ModelAdmin):
    list_display = [
        'teacher', 'academic_year', 'total_students', 'total_subjects',
        'attendance_percentage', 'average_student_performance', 'grading_completion_rate'
    ]
    list_filter = ['academic_year', 'created_at']
    search_fields = [
        'teacher__user__username', 'teacher__user__first_name', 
        'teacher__user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Teacher Information', {
            'fields': ('teacher', 'academic_year')
        }),
        ('Teaching Metrics', {
            'fields': ('total_classes', 'total_students', 'total_subjects')
        }),
        ('Attendance', {
            'fields': (
                'total_teaching_days', 'present_days', 'attendance_percentage'
            )
        }),
        ('Assignments', {
            'fields': (
                'assignments_created', 'assignments_graded', 'grading_completion_rate'
            )
        }),
        ('Student Performance', {
            'fields': (
                'average_student_performance', 'student_satisfaction_score'
            )
        }),
        ('Communication', {
            'fields': ('messages_sent', 'announcements_published')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'teacher__user', 'academic_year'
        )


@admin.register(SchoolAnalytics)
class SchoolAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'academic_year', 'total_students', 'total_teachers', 'total_classes',
        'overall_pass_percentage', 'fee_collection_rate'
    ]
    list_filter = ['academic_year', 'created_at']
    search_fields = ['academic_year__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Academic Year', {
            'fields': ('academic_year',)
        }),
        ('Student Metrics', {
            'fields': (
                'total_students', 'new_admissions', 'transfers_in', 
                'transfers_out', 'dropouts'
            )
        }),
        ('Staff Metrics', {
            'fields': (
                'total_teachers', 'total_administrators', 'total_support_staff'
            )
        }),
        ('Academic Metrics', {
            'fields': (
                'total_classes', 'total_subjects', 'average_class_size'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'overall_pass_percentage', 'average_attendance_rate'
            )
        }),
        ('Financial Metrics', {
            'fields': (
                'total_fees_expected', 'total_fees_collected', 
                'fee_collection_rate', 'outstanding_fees'
            )
        }),
        ('Infrastructure', {
            'fields': ('total_rooms', 'room_utilization_rate')
        }),
        ('Technology', {
            'fields': ('active_users', 'system_uptime')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'report_type', 'report_format', 'generated_by', 
        'generated_at', 'is_successful', 'file_size_display'
    ]
    list_filter = [
        'report_type', 'report_format', 'is_successful', 'generated_at'
    ]
    search_fields = ['name', 'description', 'generated_by__username']
    readonly_fields = [
        'generated_at', 'generation_time', 'file_size', 'error_message'
    ]
    date_hierarchy = 'generated_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': ('name', 'report_type', 'description')
        }),
        ('Parameters', {
            'fields': ('parameters', 'filters'),
            'classes': ('collapse',)
        }),
        ('Generated Report', {
            'fields': (
                'file_path', 'file_size', 'report_format', 'generation_time'
            )
        }),
        ('Generation Details', {
            'fields': ('generated_by', 'generated_at', 'is_successful', 'error_message')
        }),
    )
    
    def file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return "-"
    file_size_display.short_description = "File Size"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'generated_by', 'academic_year'
        )


# Custom admin site configuration
admin.site.site_header = "ADOM Institute Analytics"
admin.site.site_title = "ADOM Institute Analytics"
admin.site.index_title = "Analytics Dashboard"
