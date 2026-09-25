from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone
from .models import AcademicYear, Class, Student, Parent


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-2025'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError("End date must be after start date.")
            
            # Check for overlapping academic years
            if not self.instance.pk:  # Only for new instances
                overlapping = AcademicYear.objects.filter(
                    start_date__lte=end_date,
                    end_date__gte=start_date
                )
                if overlapping.exists():
                    raise forms.ValidationError("This academic year overlaps with an existing one.")
        
        return cleaned_data


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'display_name', 'academic_year', 'section', 'capacity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Class10A'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Class 10 Section A'}),
            'academic_year': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., A, B, C'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        academic_year = cleaned_data.get('academic_year')
        
        if name and academic_year:
            # Check for duplicate class names in the same academic year
            existing = Class.objects.filter(name=name, academic_year=academic_year)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError("A class with this name already exists in the selected academic year.")
        
        return cleaned_data


class StudentForm(forms.ModelForm):
    # Custom fields for user information
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'email', 'student_id', 'admission_number', 'roll_number',
            'gender', 'date_of_birth', 'phone_number', 'address', 'current_class',
            'admission_date', 'admission_status', 'is_active'
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., STU2024001'}),
            'admission_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., ADM2024001'}),
            'roll_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 001'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'current_class': forms.Select(attrs={'class': 'form-control'}),
            'admission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'admission_status': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def clean(self):
        cleaned_data = super().clean()
        date_of_birth = cleaned_data.get('date_of_birth')
        admission_date = cleaned_data.get('admission_date')
        email = cleaned_data.get('email')
        
        if date_of_birth:
            # Check if student is at least 3 years old
            age = timezone.now().date().year - date_of_birth.year
            if age < 3:
                raise forms.ValidationError("Student must be at least 3 years old.")
        
        if admission_date and date_of_birth:
            if admission_date < date_of_birth:
                raise forms.ValidationError("Admission date cannot be before date of birth.")
        
        if email:
            # Check for duplicate email
            from accounts.models import User
            existing_user = User.objects.filter(email=email)
            if self.instance.pk and self.instance.user:
                existing_user = existing_user.exclude(pk=self.instance.user.pk)
            
            if existing_user.exists():
                raise forms.ValidationError("A user with this email already exists.")
        
        return cleaned_data
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        if not self.instance.pk:  # New student
            from accounts.models import User
            user = User.objects.create_user(
                username=self.cleaned_data['email'],
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                password='changeme123'  # Temporary password
            )
            student.user = user
        else:  # Update existing student
            user = student.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.save()
        
        if commit:
            student.save()
        return student


class ParentForm(forms.ModelForm):
    # Custom fields for user information
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Parent
        fields = [
            'first_name', 'last_name', 'student', 'relationship', 'occupation',
            'phone_number', 'email', 'is_primary_contact', 'is_emergency_contact'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Engineer, Teacher'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_primary_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        is_primary_contact = cleaned_data.get('is_primary_contact')
        is_emergency_contact = cleaned_data.get('is_emergency_contact')
        email = cleaned_data.get('email')
        
        if student and is_primary_contact:
            # Check if another parent is already primary contact
            existing_primary = Parent.objects.filter(
                student=student, 
                is_primary_contact=True
            )
            if self.instance.pk:
                existing_primary = existing_primary.exclude(pk=self.instance.pk)
            
            if existing_primary.exists():
                raise forms.ValidationError("This student already has a primary contact parent.")
        
        if student and is_emergency_contact:
            # Check if another parent is already emergency contact
            existing_emergency = Parent.objects.filter(
                student=student, 
                is_emergency_contact=True
            )
            if self.instance.pk:
                existing_emergency = existing_emergency.exclude(pk=self.instance.pk)
            
            if existing_emergency.exists():
                raise forms.ValidationError("This student already has an emergency contact parent.")
        
        if email:
            # Check for duplicate email
            from accounts.models import User
            existing_user = User.objects.filter(email=email)
            if self.instance.pk and self.instance.user:
                existing_user = existing_user.exclude(pk=self.instance.user.pk)
            
            if existing_user.exists():
                raise forms.ValidationError("A user with this email already exists.")
        
        return cleaned_data
    
    def save(self, commit=True):
        parent = super().save(commit=False)
        
        if not self.instance.pk:  # New parent
            from accounts.models import User
            user = User.objects.create_user(
                username=self.cleaned_data['email'],
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                password='changeme123'  # Temporary password
            )
            parent.user = user
        else:  # Update existing parent
            user = parent.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.save()
        
        if commit:
            parent.save()
        return parent


# Search and Filter Forms
class StudentSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, ID, or admission number...'
        })
    )
    class_filter = forms.ModelChoiceField(
        queryset=Class.objects.filter(is_active=True),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status_filter = forms.ChoiceField(
        choices=[('', 'All Status')] + Student.AdmissionStatus.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    gender_filter = forms.ChoiceField(
        choices=[('', 'All Genders')] + Student.Gender.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ClassSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by class name...'
        })
    )
    academic_year_filter = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        required=False,
        empty_label="All Academic Years",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    section_filter = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by section...'
        })
    )


class ParentSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by parent name or student...'
        })
    )
    relationship_filter = forms.ChoiceField(
        choices=[('', 'All Relationships')] + Parent.Relationship.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student_filter = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class StudentClassPlacementForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    current_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, institution_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        students = Student.objects.select_related('user', 'current_class__academic_year__institution').filter(is_active=True)
        classes = Class.objects.select_related('academic_year__institution').filter(is_active=True)
        if institution_ids is not None:
            students = students.filter(current_class__academic_year__institution_id__in=institution_ids)
            classes = classes.filter(academic_year__institution_id__in=institution_ids)
        self.fields['student'].queryset = students.order_by('user__first_name', 'user__last_name')
        self.fields['current_class'].queryset = classes.order_by('academic_year__institution__name', 'display_name')

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        current_class = cleaned_data.get('current_class')
        if not student or not current_class:
            return cleaned_data

        student_institution_id = getattr(getattr(getattr(student, 'current_class', None), 'academic_year', None), 'institution_id', None)
        class_institution_id = getattr(current_class.academic_year, 'institution_id', None)
        if student_institution_id and student_institution_id != class_institution_id:
            raise forms.ValidationError('Student and class must belong to the same institution.')

        enrolled_count = current_class.students.exclude(pk=student.pk).count()
        if enrolled_count >= current_class.capacity:
            raise forms.ValidationError('Selected class is already at capacity.')

        return cleaned_data

    def save(self):
        student = self.cleaned_data['student']
        student.current_class = self.cleaned_data['current_class']
        student.save(update_fields=['current_class', 'updated_at'])
        return student
