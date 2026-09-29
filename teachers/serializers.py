from rest_framework import serializers

from .models import Teacher, Subject, TeacherSubject, Department


class TeacherSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    subject_count = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_user_details(self, obj):
        return {
            'id': obj.user_id,
            'username': obj.user.username,
            'full_name': obj.user.get_full_name(),
            'email': obj.user.email,
        }

    def get_subject_count(self, obj):
        return obj.teacher_subjects.count()


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TeacherSubjectSerializer(serializers.ModelSerializer):
    teacher_details = serializers.SerializerMethodField()
    subject_details = serializers.SerializerMethodField()

    class Meta:
        model = TeacherSubject
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_teacher_details(self, obj):
        return {
            'id': obj.teacher_id,
            'employee_id': obj.teacher.employee_id,
            'full_name': obj.teacher.user.get_full_name(),
        }

    def get_subject_details(self, obj):
        return {
            'id': obj.subject_id,
            'name': obj.subject.name,
            'code': obj.subject.code,
        }

    def validate(self, data):
        teacher = data.get('teacher', getattr(self.instance, 'teacher', None))
        subject = data.get('subject', getattr(self.instance, 'subject', None))
        if teacher and subject:
            existing = TeacherSubject.objects.filter(teacher=teacher, subject=subject)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    'This teacher is already assigned to that subject.'
                )
        return data


class DepartmentSerializer(serializers.ModelSerializer):
    head_details = serializers.SerializerMethodField()
    teacher_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_head_details(self, obj):
        if not obj.head_of_department_id:
            return None
        return {
            'id': obj.head_of_department_id,
            'employee_id': obj.head_of_department.employee_id,
            'full_name': obj.head_of_department.user.get_full_name(),
        }

    def get_teacher_count(self, obj):
        # teacher_departments is the reverse of TeacherDepartment.department, so
        # it is the set of teachers assigned to this department. The related
        # name on Teacher is headed_departments (departments this teacher heads)
        # and does not exist on Department.
        return obj.teacher_departments.count()
