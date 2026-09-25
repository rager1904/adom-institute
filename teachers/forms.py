from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from students.models import Class
from timetable.models import ClassSchedule, Room, TimeSlot
from .models import Teacher, Subject, TeacherSubject, Department, TeacherDepartment

User = get_user_model()


class TeacherForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    
    class Meta:
        model = Teacher
        fields = [
            'first_name', 'last_name', 'email', 'employee_id', 'employment_type',
            'employment_status', 'joining_date', 'contract_end_date',
            'qualification', 'specialization', 'experience_years',
            'phone_number', 'emergency_contact', 'address',
            'is_class_teacher', 'is_head_of_department'
        ]
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Teacher.objects.filter(employee_id=employee_id).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('An employee with this ID already exists.')
        return employee_id
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.user.pk if self.instance.pk and self.instance.user else None).exists():
            raise ValidationError('A user with this email already exists.')
        return email
    
    def clean_contract_end_date(self):
        joining_date = self.cleaned_data.get('joining_date')
        contract_end_date = self.cleaned_data.get('contract_end_date')
        
        if contract_end_date and joining_date and contract_end_date <= joining_date:
            raise ValidationError('Contract end date must be after joining date.')
        
        return contract_end_date
    
    def clean_experience_years(self):
        experience_years = self.cleaned_data.get('experience_years')
        if experience_years > 50:
            raise ValidationError('Experience years cannot exceed 50.')
        return experience_years
    
    def save(self, commit=True):
        teacher = super().save(commit=False)
        
        if self.instance.pk:
            # Update existing user
            user = self.instance.user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.save()
        else:
            # Create new user
            user = User.objects.create_user(
                username=self.cleaned_data['email'],
                email=self.cleaned_data['email'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                password='changeme123'  # Default password, should be changed
            )
            teacher.user = user
        
        if commit:
            teacher.save()
        return teacher


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if Subject.objects.filter(code=code).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('A subject with this code already exists.')
        return code.upper()
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Subject.objects.filter(name=name).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('A subject with this name already exists.')
        return name


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'head_of_department', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if Department.objects.filter(code=code).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('A department with this code already exists.')
        return code.upper()
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Department.objects.filter(name=name).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('A department with this name already exists.')
        return name


class TeacherSubjectForm(forms.ModelForm):
    class Meta:
        model = TeacherSubject
        fields = ['teacher', 'subject', 'is_primary']
    
    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        subject = cleaned_data.get('subject')
        is_primary = cleaned_data.get('is_primary')
        
        if teacher and subject:
            # Check if this assignment already exists
            existing = TeacherSubject.objects.filter(
                teacher=teacher, 
                subject=subject
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            if existing.exists():
                raise ValidationError('This teacher is already assigned to this subject.')
            
            # If setting as primary, remove primary from other subjects for this teacher
            if is_primary:
                TeacherSubject.objects.filter(
                    teacher=teacher, 
                    is_primary=True
                ).exclude(pk=self.instance.pk if self.instance.pk else None).update(is_primary=False)
        
        return cleaned_data


class TeacherDepartmentForm(forms.ModelForm):
    class Meta:
        model = TeacherDepartment
        fields = ['teacher', 'department']
    
    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        department = cleaned_data.get('department')
        
        if teacher and department:
            # Check if this assignment already exists
            existing = TeacherDepartment.objects.filter(
                teacher=teacher, 
                department=department
            ).exclude(pk=self.instance.pk if self.instance.pk else None)
            
            if existing.exists():
                raise ValidationError('This teacher is already assigned to this department.')
        
        return cleaned_data


# Search and Filter Forms
class TeacherSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, employee ID, or email...',
            'class': 'form-control'
        })
    )
    employment_type_filter = forms.ChoiceField(
        choices=[('', 'All Types')] + Teacher.EmploymentType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    employment_status_filter = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Teacher.EmploymentStatus.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    qualification_filter = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Filter by qualification...',
            'class': 'form-control'
        })
    )


class SubjectSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name or code...',
            'class': 'form-control'
        })
    )
    is_active_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class DepartmentSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name or code...',
            'class': 'form-control'
        })
    )
    is_active_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    has_head_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Has Head'), ('False', 'No Head')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class TeacherClassSubjectAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        label='Class',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    is_primary_subject = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, institution_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        teachers = Teacher.objects.select_related('user').filter(
            employment_status=Teacher.EmploymentStatus.ACTIVE,
        )
        classes = Class.objects.select_related('academic_year__institution').filter(is_active=True)
        if institution_ids is not None:
            teachers = teachers.filter(user__institution_memberships__institution_id__in=institution_ids)
            classes = classes.filter(academic_year__institution_id__in=institution_ids)

        self.fields['teacher'].queryset = teachers.distinct().order_by('user__first_name', 'user__last_name')
        self.fields['class_obj'].queryset = classes.order_by('academic_year__institution__name', 'display_name')
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')
        self.fields['room'].queryset = Room.objects.filter(is_active=True).order_by('name')
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_break=False).order_by('day', 'start_time')

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        class_obj = cleaned_data.get('class_obj')
        room = cleaned_data.get('room')
        time_slot = cleaned_data.get('time_slot')

        if teacher and class_obj:
            teacher_institution_ids = set(
                teacher.user.institution_memberships.filter(is_active=True).values_list('institution_id', flat=True)
            )
            class_institution_id = getattr(class_obj.academic_year, 'institution_id', None)
            if class_institution_id not in teacher_institution_ids:
                raise forms.ValidationError('Teacher and class must belong to the same institution.')

        if class_obj and time_slot and ClassSchedule.objects.filter(
            class_obj=class_obj,
            time_slot=time_slot,
            is_active=True,
        ).exists():
            raise forms.ValidationError('This class already has a schedule at the selected time.')

        if teacher and time_slot and ClassSchedule.objects.filter(
            teacher=teacher,
            time_slot=time_slot,
            is_active=True,
        ).exists():
            raise forms.ValidationError('This teacher is already scheduled at the selected time.')

        if room and time_slot and ClassSchedule.objects.filter(
            room=room,
            time_slot=time_slot,
            is_active=True,
        ).exists():
            raise forms.ValidationError('This room is already occupied at the selected time.')

        return cleaned_data

    def save(self):
        teacher = self.cleaned_data['teacher']
        subject = self.cleaned_data['subject']
        teacher_subject, _ = TeacherSubject.objects.get_or_create(
            teacher=teacher,
            subject=subject,
            defaults={'is_primary': self.cleaned_data.get('is_primary_subject') or False},
        )
        if self.cleaned_data.get('is_primary_subject') and not teacher_subject.is_primary:
            TeacherSubject.objects.filter(teacher=teacher, is_primary=True).exclude(pk=teacher_subject.pk).update(is_primary=False)
            teacher_subject.is_primary = True
            teacher_subject.save(update_fields=['is_primary'])

        return ClassSchedule.objects.create(
            class_obj=self.cleaned_data['class_obj'],
            subject=subject,
            teacher=teacher,
            room=self.cleaned_data['room'],
            time_slot=self.cleaned_data['time_slot'],
            is_active=True,
        )
