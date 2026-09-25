from rest_framework import serializers
from django.utils import timezone
from .models import AcademicYear, Class, Student, Parent


class AcademicYearSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    class_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AcademicYear
        fields = '__all__'
    
    def get_duration_days(self, obj):
        return (obj.end_date - obj.start_date).days
    
    def get_class_count(self, obj):
        return obj.classes.count()
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("End date must be after start date.")
            
            # Check for overlapping academic years
            if not self.instance:  # Only for new instances
                overlapping = AcademicYear.objects.filter(
                    start_date__lte=end_date,
                    end_date__gte=start_date
                )
                if overlapping.exists():
                    raise serializers.ValidationError("This academic year overlaps with an existing one.")
        
        return data


class AcademicYear_CreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_active']


class ClassSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    student_count = serializers.SerializerMethodField()
    capacity_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = '__all__'
    
    def get_student_count(self, obj):
        return obj.students.count()
    
    def get_capacity_available(self, obj):
        return obj.capacity - obj.students.count()
    
    def validate(self, data):
        name = data.get('name')
        academic_year = data.get('academic_year')
        
        if name and academic_year:
            # Check for duplicate class names in the same academic year
            existing = Class.objects.filter(name=name, academic_year=academic_year)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError("A class with this name already exists in the selected academic year.")
        
        return data


class Class_CreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = ['name', 'display_name', 'academic_year', 'section', 'capacity', 'is_active']


class StudentSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    current_class_name = serializers.CharField(source='current_class.display_name', read_only=True)
    age = serializers.SerializerMethodField()
    parent_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = '__all__'
    
    def get_age(self, obj):
        today = timezone.now().date()
        age = today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return age
    
    def get_parent_count(self, obj):
        return obj.parents.count()
    
    def validate(self, data):
        date_of_birth = data.get('date_of_birth')
        admission_date = data.get('admission_date')
        
        if date_of_birth:
            # Check if student is at least 3 years old
            age = timezone.now().date().year - date_of_birth.year
            if age < 3:
                raise serializers.ValidationError("Student must be at least 3 years old.")
        
        if admission_date and date_of_birth:
            if admission_date < date_of_birth:
                raise serializers.ValidationError("Admission date cannot be before date of birth.")
        
        return data


class Student_CreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'email', 'student_id', 'admission_number', 'roll_number',
            'gender', 'date_of_birth', 'phone_number', 'address', 'current_class',
            'admission_date', 'admission_status', 'is_active'
        ]
    
    def create(self, validated_data):
        from accounts.models import InstitutionMembership, User
        
        # Extract user data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type=User.UserType.STUDENT,
            password='changeme123'
        )
        
        # Create student
        student = Student.objects.create(user=user, **validated_data)
        institution = getattr(getattr(student.current_class, 'academic_year', None), 'institution', None)
        if institution:
            InstitutionMembership.objects.get_or_create(
                institution=institution,
                user=user,
                defaults={'role': InstitutionMembership.MembershipRole.STUDENT},
            )
        return student


class ParentSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    
    class Meta:
        model = Parent
        fields = '__all__'
    
    def validate(self, data):
        student = data.get('student')
        is_primary_contact = data.get('is_primary_contact')
        is_emergency_contact = data.get('is_emergency_contact')
        
        if student and is_primary_contact:
            # Check if another parent is already primary contact
            existing_primary = Parent.objects.filter(
                student=student, 
                is_primary_contact=True
            )
            if self.instance:
                existing_primary = existing_primary.exclude(pk=self.instance.pk)
            
            if existing_primary.exists():
                raise serializers.ValidationError("This student already has a primary contact parent.")
        
        if student and is_emergency_contact:
            # Check if another parent is already emergency contact
            existing_emergency = Parent.objects.filter(
                student=student, 
                is_emergency_contact=True
            )
            if self.instance:
                existing_emergency = existing_emergency.exclude(pk=self.instance.pk)
            
            if existing_emergency.exists():
                raise serializers.ValidationError("This student already has an emergency contact parent.")
        
        return data


class Parent_CreateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    
    class Meta:
        model = Parent
        fields = [
            'first_name', 'last_name', 'student', 'relationship', 'occupation',
            'phone_number', 'email', 'is_primary_contact', 'is_emergency_contact'
        ]
    
    def create(self, validated_data):
        from accounts.models import InstitutionMembership, User
        
        # Extract user data
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type=User.UserType.PARENT,
            password='changeme123'
        )
        
        # Create parent
        parent = Parent.objects.create(user=user, **validated_data)
        institution = getattr(getattr(parent.student.current_class, 'academic_year', None), 'institution', None)
        if institution:
            InstitutionMembership.objects.get_or_create(
                institution=institution,
                user=user,
                defaults={'role': InstitutionMembership.MembershipRole.PARENT},
            )
        return parent


# Nested Serializers for detailed views
class StudentDetailSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    current_class_name = serializers.CharField(source='current_class.display_name', read_only=True)
    age = serializers.SerializerMethodField()
    parents = ParentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Student
        fields = '__all__'
    
    def get_age(self, obj):
        today = timezone.now().date()
        age = today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return age


class ClassDetailSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    student_count = serializers.SerializerMethodField()
    capacity_available = serializers.SerializerMethodField()
    students = StudentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Class
        fields = '__all__'
    
    def get_student_count(self, obj):
        return obj.students.count()
    
    def get_capacity_available(self, obj):
        return obj.capacity - obj.students.count()


class AcademicYearDetailSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    class_count = serializers.SerializerMethodField()
    classes = ClassSerializer(many=True, read_only=True)
    
    class Meta:
        model = AcademicYear
        fields = '__all__'
    
    def get_duration_days(self, obj):
        return (obj.end_date - obj.start_date).days
    
    def get_class_count(self, obj):
        return obj.classes.count()


# Summary and Report Serializers
class StudentSummarySerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    current_class_name = serializers.CharField(source='current_class.display_name', read_only=True)
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = ['id', 'student_id', 'user_full_name', 'current_class_name', 'admission_status', 'age', 'is_active']
    
    def get_age(self, obj):
        today = timezone.now().date()
        age = today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return age


class ClassSummarySerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    student_count = serializers.SerializerMethodField()
    capacity_utilization = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = ['id', 'name', 'display_name', 'academic_year_name', 'section', 'capacity', 'student_count', 'capacity_utilization', 'is_active']
    
    def get_student_count(self, obj):
        return obj.students.count()
    
    def get_capacity_utilization(self, obj):
        if obj.capacity > 0:
            return round((obj.students.count() / obj.capacity) * 100, 1)
        return 0


class AcademicYearSummarySerializer(serializers.ModelSerializer):
    class_count = serializers.SerializerMethodField()
    total_students = serializers.SerializerMethodField()
    
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active', 'class_count', 'total_students']
    
    def get_class_count(self, obj):
        return obj.classes.count()
    
    def get_total_students(self, obj):
        return sum(class_obj.students.count() for class_obj in obj.classes.all())


# Dashboard and Statistics Serializers
class DashboardStatsSerializer(serializers.Serializer):
    total_students = serializers.IntegerField()
    active_students = serializers.IntegerField()
    pending_admissions = serializers.IntegerField()
    total_classes = serializers.IntegerField()
    total_parents = serializers.IntegerField()
    students_by_gender = serializers.DictField()
    students_by_status = serializers.DictField()
    recent_admissions = StudentSummarySerializer(many=True)


class StudentReportSerializer(serializers.ModelSerializer):
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    current_class_name = serializers.CharField(source='current_class.display_name', read_only=True)
    age = serializers.SerializerMethodField()
    days_since_admission = serializers.SerializerMethodField()
    parent_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'student_id', 'admission_number', 'user_full_name', 'current_class_name',
            'gender', 'age', 'admission_date', 'days_since_admission', 'admission_status',
            'parent_count', 'is_active'
        ]
    
    def get_age(self, obj):
        today = timezone.now().date()
        age = today.year - obj.date_of_birth.year - ((today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day))
        return age
    
    def get_days_since_admission(self, obj):
        return (timezone.now().date() - obj.admission_date).days
    
    def get_parent_count(self, obj):
        return obj.parents.count()
