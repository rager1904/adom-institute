from rest_framework import serializers
from .models import (
    AnalyticsEvent, StudentPerformance, ClassPerformance, 
    TeacherPerformance, SchoolAnalytics, Report
)


class AnalyticsEventSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = AnalyticsEvent
        fields = [
            'id', 'user', 'user_name', 'event_type', 'event_type_display',
            'event_data', 'ip_address', 'user_agent', 'session_id', 'created_at'
        ]
        read_only_fields = ['created_at']


class StudentPerformanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = StudentPerformance
        fields = [
            'id', 'student', 'student_name', 'student_id', 'academic_year', 
            'academic_year_name', 'class_obj', 'class_name', 'total_subjects',
            'total_marks', 'obtained_marks', 'percentage', 'grade', 'rank_in_class',
            'class_average', 'total_days', 'present_days', 'absent_days',
            'attendance_percentage', 'total_assignments', 'submitted_assignments',
            'assignment_completion_rate', 'total_fees', 'paid_fees', 'fee_payment_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ClassPerformanceSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = ClassPerformance
        fields = [
            'id', 'class_obj', 'class_name', 'academic_year', 'academic_year_name',
            'total_students', 'average_percentage', 'highest_percentage', 'lowest_percentage',
            'grade_a_count', 'grade_b_count', 'grade_c_count', 'grade_d_count', 'grade_f_count',
            'average_attendance', 'total_attendance_days', 'total_fees_expected',
            'total_fees_collected', 'fee_collection_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TeacherPerformanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = TeacherPerformance
        fields = [
            'id', 'teacher', 'teacher_name', 'academic_year', 'academic_year_name',
            'total_classes', 'total_students', 'total_subjects', 'total_teaching_days',
            'present_days', 'attendance_percentage', 'assignments_created',
            'assignments_graded', 'grading_completion_rate', 'average_student_performance',
            'student_satisfaction_score', 'messages_sent', 'announcements_published',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SchoolAnalyticsSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = SchoolAnalytics
        fields = [
            'id', 'academic_year', 'academic_year_name', 'total_students', 'new_admissions',
            'transfers_in', 'transfers_out', 'dropouts', 'total_teachers',
            'total_administrators', 'total_support_staff', 'total_classes', 'total_subjects',
            'average_class_size', 'overall_pass_percentage', 'average_attendance_rate',
            'total_fees_expected', 'total_fees_collected', 'fee_collection_rate',
            'outstanding_fees', 'total_rooms', 'room_utilization_rate', 'active_users',
            'system_uptime', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    report_format_display = serializers.CharField(source='get_report_format_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'report_type', 'report_type_display', 'description',
            'parameters', 'filters', 'file_path', 'file_url', 'file_size',
            'report_format', 'report_format_display', 'generated_by', 'generated_by_name',
            'generated_at', 'generation_time', 'is_successful', 'error_message',
            'created_at'
        ]
        read_only_fields = ['generated_at', 'generation_time', 'file_size', 'created_at']
    
    def get_file_url(self, obj):
        if obj.file_path:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_path.url)
        return None


# Specialized serializers for analytics dashboard
class DashboardStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    total_teachers = serializers.IntegerField()
    total_classes = serializers.IntegerField()
    total_subjects = serializers.IntegerField()
    average_attendance = serializers.DecimalField(max_digits=5, decimal_places=2)
    overall_pass_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    fee_collection_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    active_users_today = serializers.IntegerField()
    total_reports_generated = serializers.IntegerField()


class PerformanceTrendSerializer(serializers.Serializer):
    period = serializers.CharField()
    academic_performance = serializers.DecimalField(max_digits=5, decimal_places=2)
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    fee_collection = serializers.DecimalField(max_digits=5, decimal_places=2)


class GradeDistributionSerializer(serializers.Serializer):
    grade = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)


class ClassComparisonSerializer(serializers.Serializer):
    class_name = serializers.CharField()
    average_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    attendance_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    student_count = serializers.IntegerField()


class TeacherPerformanceSummarySerializer(serializers.Serializer):
    teacher_name = serializers.CharField()
    total_students = serializers.IntegerField()
    average_student_performance = serializers.DecimalField(max_digits=5, decimal_places=2)
    attendance_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    grading_completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class ReportGenerationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            'name', 'report_type', 'description', 'parameters', 'filters', 'report_format'
        ]
    
    def validate_parameters(self, value):
        # Add validation for report parameters
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a dictionary")
        return value
    
    def validate_filters(self, value):
        # Add validation for report filters
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")
        return value


class AnalyticsFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    academic_year = serializers.IntegerField(required=False)
    class_id = serializers.IntegerField(required=False)
    teacher_id = serializers.IntegerField(required=False)
    student_id = serializers.IntegerField(required=False)
    event_type = serializers.CharField(required=False)
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date")
        
        return data
