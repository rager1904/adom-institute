from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ExamType, Exam, ExamSubject, Grade, StudentExamResult,
    Assignment, StudentAssignment
)


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'weightage', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    fieldsets = (
        (None, {'fields': ('name', 'description', 'weightage', 'is_active')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'academic_year', 'class_obj', 'start_date', 'end_date', 'is_active')
    list_filter = ('exam_type', 'academic_year', 'class_obj', 'is_active', 'start_date')
    search_fields = ('name', 'exam_type__name', 'class_obj__name')
    date_hierarchy = 'start_date'
    ordering = ('-start_date',)
    
    fieldsets = (
        ('Basic Information', {'fields': ('name', 'exam_type', 'academic_year', 'class_obj')}),
        ('Schedule', {'fields': ('start_date', 'end_date')}),
        ('Marks Configuration', {'fields': ('total_marks', 'passing_marks')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ('exam', 'subject', 'max_marks', 'passing_marks', 'exam_date', 'duration')
    list_filter = ('exam__exam_type', 'subject', 'exam_date')
    search_fields = ('exam__name', 'subject__name')
    date_hierarchy = 'exam_date'
    ordering = ('-exam_date',)
    
    fieldsets = (
        ('Exam Information', {'fields': ('exam', 'subject')}),
        ('Marks Configuration', {'fields': ('max_marks', 'passing_marks')}),
        ('Schedule', {'fields': ('exam_date', 'duration')}),
    )


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_marks', 'max_marks', 'grade_point', 'description')
    list_filter = ('grade_point',)
    search_fields = ('name', 'description')
    ordering = ('min_marks',)
    
    fieldsets = (
        ('Grade Information', {'fields': ('name', 'description')}),
        ('Marks Range', {'fields': ('min_marks', 'max_marks')}),
        ('Grade Point', {'fields': ('grade_point',)}),
    )


@admin.register(StudentExamResult)
class StudentExamResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam_subject', 'marks_obtained', 'percentage', 'grade', 'is_pass', 'created_by')
    list_filter = ('exam_subject__exam__exam_type', 'exam_subject__subject', 'grade', 'created_at')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'exam_subject__exam__name')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Student & Exam', {'fields': ('student', 'exam_subject')}),
        ('Results', {'fields': ('marks_obtained', 'grade', 'remarks')}),
        ('Created By', {'fields': ('created_by',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'percentage', 'is_pass')
    
    def percentage(self, obj):
        return f"{obj.percentage:.2f}%"
    percentage.short_description = 'Percentage'
    
    def is_pass(self, obj):
        if obj.is_pass:
            return format_html('<span style="color: green;">✓ Pass</span>')
        return format_html('<span style="color: red;">✗ Fail</span>')
    is_pass.short_description = 'Pass/Fail'


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'class_obj', 'teacher', 'due_date', 'max_marks', 'is_active')
    list_filter = ('subject', 'class_obj', 'teacher', 'is_active', 'due_date')
    search_fields = ('title', 'subject__name', 'class_obj__name', 'teacher__user__first_name')
    date_hierarchy = 'due_date'
    ordering = ('-due_date',)
    
    fieldsets = (
        ('Assignment Details', {'fields': ('title', 'description', 'subject', 'class_obj', 'teacher')}),
        ('Configuration', {'fields': ('due_date', 'max_marks', 'attachment')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StudentAssignment)
class StudentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'submitted_at', 'is_late', 'marks_obtained', 'is_graded')
    list_filter = ('assignment__subject', 'assignment__class_obj', 'graded_at')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'assignment__title')
    date_hierarchy = 'submitted_at'
    ordering = ('-submitted_at',)
    
    fieldsets = (
        ('Submission Details', {'fields': ('student', 'assignment')}),
        ('Submission', {'fields': ('submission_file', 'submission_text', 'submitted_at')}),
        ('Grading', {'fields': ('marks_obtained', 'feedback', 'graded_by', 'graded_at')}),
    )
    
    readonly_fields = ('submitted_at', 'is_late', 'is_graded')
    
    def is_late(self, obj):
        if obj.is_late:
            return format_html('<span style="color: red;">Late</span>')
        return format_html('<span style="color: green;">On Time</span>')
    is_late.short_description = 'Submission Status'
    
    def is_graded(self, obj):
        if obj.is_graded:
            return format_html('<span style="color: green;">✓ Graded</span>')
        return format_html('<span style="color: orange;">Pending</span>')
    is_graded.short_description = 'Grading Status'
