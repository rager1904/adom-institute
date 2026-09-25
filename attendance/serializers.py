from rest_framework import serializers
from .models import Attendance, ClassAttendance, TeacherAttendance, LeaveRequest
from students.models import Student
from teachers.models import Teacher


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Student
        fields = ['id', 'full_name', 'student_id']


class TeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Teacher
        fields = ['id', 'full_name', 'employee_id']


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'date', 'status', 'remarks',
            'marked_by', 'marked_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['marked_by', 'created_at', 'updated_at']


class AttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['student', 'date', 'status', 'remarks']
    
    def create(self, validated_data):
        validated_data['marked_by'] = self.context['request'].user.teacher_profile
        return super().create(validated_data)


class BulkAttendanceSerializer(serializers.Serializer):
    class_obj = serializers.IntegerField()
    date = serializers.DateField()
    attendances = serializers.ListField(
        child=serializers.DictField(),
        write_only=True
    )
    
    def validate_attendances(self, value):
        if not value:
            raise serializers.ValidationError("At least one attendance record is required.")
        return value


class ClassAttendanceSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    marked_by_name = serializers.CharField(source='marked_by.user.get_full_name', read_only=True)
    attendance_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = ClassAttendance
        fields = [
            'id', 'class_obj', 'class_name', 'date', 'total_students',
            'present_count', 'absent_count', 'late_count', 'attendance_percentage',
            'marked_by', 'marked_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['marked_by', 'created_at', 'updated_at']


class ClassAttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassAttendance
        fields = ['class_obj', 'date', 'total_students', 'present_count', 'absent_count', 'late_count']
    
    def create(self, validated_data):
        validated_data['marked_by'] = self.context['request'].user.teacher_profile
        return super().create(validated_data)


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    
    class Meta:
        model = TeacherAttendance
        fields = [
            'id', 'teacher', 'teacher_name', 'date', 'status',
            'check_in_time', 'check_out_time', 'remarks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TeacherAttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherAttendance
        fields = ['teacher', 'date', 'status', 'check_in_time', 'check_out_time', 'remarks']


class LeaveRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.user.get_full_name', read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'student', 'student_name', 'teacher', 'teacher_name',
            'leave_type', 'start_date', 'end_date', 'duration_days', 'reason',
            'supporting_document', 'status', 'approved_by', 'approved_by_name',
            'approved_at', 'remarks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['approved_by', 'approved_at', 'created_at', 'updated_at']


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason', 'supporting_document']
    
    def create(self, validated_data):
        user = self.context['request'].user
        if hasattr(user, 'student_profile'):
            validated_data['student'] = user.student_profile
        elif hasattr(user, 'teacher_profile'):
            validated_data['teacher'] = user.teacher_profile
        else:
            raise serializers.ValidationError("User must be either a student or teacher.")
        
        return super().create(validated_data)


class LeaveApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['status', 'remarks']
    
    def update(self, instance, validated_data):
        if validated_data.get('status') == LeaveRequest.LeaveStatus.APPROVED:
            validated_data['approved_by'] = self.context['request'].user.teacher_profile
            from django.utils import timezone
            validated_data['approved_at'] = timezone.now()
        
        return super().update(instance, validated_data)


class AttendanceSummarySerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    present_count = serializers.IntegerField()
    absent_count = serializers.IntegerField()
    late_count = serializers.IntegerField()
    attendance_percentage = serializers.FloatField()
    date = serializers.DateField()


class LeaveRequestSummarySerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    approved_count = serializers.IntegerField()
    rejected_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()
    period = serializers.CharField()


class AttendanceReportSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    total_days = serializers.IntegerField()
    present_days = serializers.IntegerField()
    absent_days = serializers.IntegerField()
    late_days = serializers.IntegerField()
    attendance_percentage = serializers.FloatField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
