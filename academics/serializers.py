from rest_framework import serializers
from .models import (
    ExamType, Exam, ExamSubject, Grade, StudentExamResult,
    Assignment, StudentAssignment
)


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = '__all__'
        read_only_fields = ('id',)


class ExamSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    
    class Meta:
        model = ExamSubject
        fields = '__all__'
        read_only_fields = ('id', 'created_at')


class ExamSerializer(serializers.ModelSerializer):
    exam_subjects = ExamSubjectSerializer(many=True, read_only=True)
    exam_type_name = serializers.CharField(source='exam_type.name', read_only=True)
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = Exam
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class StudentExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    exam_name = serializers.CharField(source='exam_subject.exam.name', read_only=True)
    subject_name = serializers.CharField(source='exam_subject.subject.name', read_only=True)
    grade_name = serializers.CharField(source='grade.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = StudentExamResult
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'percentage', 'is_pass')


class AssignmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    teacher_name = serializers.CharField(source='teacher.user.get_full_name', read_only=True)
    submission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_submission_count(self, obj):
        return obj.student_submissions.count()


class StudentAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)
    subject_name = serializers.CharField(source='assignment.subject.name', read_only=True)
    graded_by_name = serializers.CharField(source='graded_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = StudentAssignment
        fields = '__all__'
        read_only_fields = ('id', 'submitted_at', 'is_late', 'is_graded')


class BulkGradeEntrySerializer(serializers.Serializer):
    exam_subject_id = serializers.IntegerField()
    grades = serializers.ListField(
        child=serializers.DictField()
    )
    
    def validate_grades(self, value):
        for grade in value:
            if 'student_id' not in grade or 'marks_obtained' not in grade:
                raise serializers.ValidationError("Each grade must contain student_id and marks_obtained")
        return value


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAssignment
        fields = ('assignment', 'submission_file', 'submission_text')
    
    def validate(self, attrs):
        assignment = attrs.get('assignment')
        submission_file = attrs.get('submission_file')
        submission_text = attrs.get('submission_text')
        
        if not submission_file and not submission_text:
            raise serializers.ValidationError("Either submission file or text is required")
        
        return attrs


class AssignmentGradingSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAssignment
        fields = ('marks_obtained', 'feedback')
    
    def validate_marks_obtained(self, value):
        assignment = self.instance.assignment
        if value > assignment.max_marks:
            raise serializers.ValidationError(f"Marks cannot exceed {assignment.max_marks}")
        if value < 0:
            raise serializers.ValidationError("Marks cannot be negative")
        return value


class ExamResultSummarySerializer(serializers.Serializer):
    exam_id = serializers.IntegerField()
    total_students = serializers.IntegerField()
    passed_students = serializers.IntegerField()
    failed_students = serializers.IntegerField()
    average_percentage = serializers.FloatField()
    highest_percentage = serializers.FloatField()
    lowest_percentage = serializers.FloatField()
    grade_distribution = serializers.DictField()


class AssignmentSummarySerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField()
    total_students = serializers.IntegerField()
    submitted_students = serializers.IntegerField()
    pending_students = serializers.IntegerField()
    graded_submissions = serializers.IntegerField()
    average_marks = serializers.FloatField()
    submission_rate = serializers.FloatField()
