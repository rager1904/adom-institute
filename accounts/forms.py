from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Institution, InstitutionMembership, TuitionEnquiry, User, UserProfile
from students.models import AcademicYear, Class, Student
from teachers.models import Teacher
from fees.models import FeeCategory, FeeStructure


class TuitionEnquiryForm(forms.ModelForm):
    consent = forms.BooleanField(
        required=True,
        label='I consent to ADOM Institute contacting me about this tuition request.',
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = TuitionEnquiry
        fields = (
            'guardian_name', 'learner_name', 'current_school', 'phone_number', 'email',
            'learning_level', 'subjects', 'tuition_format', 'location',
            'preferred_schedule', 'notes',
        )
        labels = {
            'guardian_name': 'Parent or guardian name',
            'learner_name': 'Learner name',
            'current_school': "Learner's current school",
            'phone_number': 'Phone or WhatsApp number',
            'learning_level': 'Current learning level',
            'subjects': 'Subjects requiring tuition',
            'tuition_format': 'Preferred class format',
            'preferred_schedule': 'Preferred days and times',
            'notes': 'Anything else we should know?',
        }
        widgets = {
            'guardian_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'learner_name': forms.TextInput(attrs={'autocomplete': 'off'}),
            'current_school': forms.TextInput(attrs={'autocomplete': 'organization', 'placeholder': 'Enter the school name'}),
            'phone_number': forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '+260 ...'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'learning_level': forms.Select,
            'subjects': forms.TextInput(attrs={'placeholder': 'e.g. Mathematics, English and Science'}),
            'tuition_format': forms.Select,
            'location': forms.Select,
            'preferred_schedule': forms.TextInput(attrs={'placeholder': 'e.g. Weekdays after 15:00'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise ValidationError('Your request could not be submitted.')
        return ''

    def clean_phone_number(self):
        value = ''.join(self.cleaned_data['phone_number'].split())
        allowed = value.lstrip('+').replace('-', '')
        if not allowed.isdigit() or not 9 <= len(allowed) <= 15:
            raise ValidationError('Enter a valid phone number, including the country code where applicable.')
        return value


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
    )
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.none(),
        required=True,
        empty_label='Select school',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    current_class = forms.ModelChoiceField(
        queryset=Class.objects.none(),
        required=False,
        empty_label='Auto assign if available',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    gender = forms.ChoiceField(
        choices=Student.Gender.choices,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
    )
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
    
    class Meta:
        model = User
        fields = (
            'email', 'first_name', 'last_name', 'institution', 'current_class',
            'gender', 'phone_number', 'date_of_birth', 'address', 'password1', 'password2'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['institution'].queryset = Institution.objects.filter(
            is_active=True, status=Institution.Status.APPROVED
        ).order_by('name')
        self.fields['current_class'].queryset = Class.objects.filter(
            is_active=True,
            academic_year__institution__is_active=True,
            academic_year__institution__status=Institution.Status.APPROVED,
        ).select_related('academic_year', 'academic_year__institution').order_by(
            'academic_year__institution__name',
            'display_name',
        )
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        institution = cleaned_data.get('institution')
        current_class = cleaned_data.get('current_class')
        date_of_birth = cleaned_data.get('date_of_birth')

        if current_class and institution:
            class_institution_id = getattr(current_class.academic_year, 'institution_id', None)
            if class_institution_id != institution.id:
                self.add_error('current_class', 'Selected class does not belong to the selected school.')

        if date_of_birth:
            today = timezone.localdate()
            age = today.year - date_of_birth.year
            if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
                age -= 1
            if age < 3:
                self.add_error('date_of_birth', 'Student must be at least 3 years old.')

        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.user_type = User.UserType.STUDENT
        user.phone_number = self.cleaned_data.get('phone_number') or ''
        user.date_of_birth = self.cleaned_data.get('date_of_birth')
        user.address = self.cleaned_data.get('address') or ''
        
        if commit:
            with transaction.atomic():
                user.save()
                UserProfile.objects.get_or_create(user=user)
                institution = self.cleaned_data['institution']
                student_id, admission_number = self._next_student_identifiers(institution)
                Student.objects.create(
                    user=user,
                    student_id=student_id,
                    admission_number=admission_number,
                    roll_number=self._next_roll_number(institution),
                    gender=self.cleaned_data['gender'],
                    date_of_birth=self.cleaned_data['date_of_birth'],
                    phone_number=user.phone_number,
                    address=user.address,
                    current_class=self._selected_or_default_class(institution),
                    admission_date=timezone.localdate(),
                    admission_status=Student.AdmissionStatus.PENDING,
                    is_active=True,
                )
                InstitutionMembership.objects.get_or_create(
                    institution=institution,
                    user=user,
                    defaults={'role': InstitutionMembership.MembershipRole.STUDENT},
                )
        return user

    @staticmethod
    def _institution_prefix(institution):
        return ''.join(char for char in institution.code.upper() if char.isalnum()) or 'STU'

    def _selected_or_default_class(self, institution):
        current_class = self.cleaned_data.get('current_class')
        if current_class:
            return current_class
        return Class.objects.filter(
            academic_year__institution=institution,
            is_active=True,
        ).order_by('display_name').first()

    def _next_student_identifiers(self, institution):
        prefix = self._institution_prefix(institution)
        number = self._next_student_sequence(prefix)

        while True:
            suffix = f'{number:03d}'
            student_id = f'{prefix[:17]}{suffix}'
            admission_number = self._format_admission_number(institution, student_id, suffix)
            if (
                not Student.objects.filter(student_id=student_id).exists()
                and not Student.objects.filter(admission_number=admission_number).exists()
            ):
                return student_id, admission_number
            number += 1

    def _next_student_sequence(self, prefix):
        existing_ids = Student.objects.filter(
            student_id__startswith=prefix,
        ).values_list('student_id', flat=True)
        numbers = []
        for student_id in existing_ids:
            suffix = student_id[len(prefix):]
            if suffix.isdigit():
                numbers.append(int(suffix))
        return (max(numbers) + 1) if numbers else 1

    def _format_admission_number(self, institution, student_id, suffix):
        prefix = self._institution_prefix(institution)
        existing = Student.objects.filter(
            current_class__academic_year__institution=institution,
        ).order_by('-created_at').values_list('admission_number', flat=True).first()

        if existing and existing.startswith(f'{prefix[:1]}ADM'):
            return f'{prefix[:1]}ADM{suffix}'[:20]
        return f'ADM-{student_id}'[:20]

    def _next_roll_number(self, institution):
        prefix = self._institution_prefix(institution)
        number = self._next_student_sequence(prefix)
        return f'{number:03d}'


class TeacherRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
    )
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.none(),
        required=True,
        empty_label='Select school',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    employment_type = forms.ChoiceField(
        choices=Teacher.EmploymentType.choices,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    joining_date = forms.DateField(
        required=True,
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    qualification = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    specialization = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    experience_years = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
    )
    emergency_contact = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
    )
    address = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    class Meta:
        model = User
        fields = (
            'email', 'first_name', 'last_name', 'institution', 'employment_type',
            'joining_date', 'qualification', 'specialization', 'experience_years',
            'phone_number', 'emergency_contact', 'address', 'password1', 'password2'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['institution'].queryset = Institution.objects.filter(
            is_active=True, status=Institution.Status.APPROVED
        ).order_by('name')
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.user_type = User.UserType.TEACHER
        user.phone_number = self.cleaned_data['phone_number']
        user.address = self.cleaned_data['address']

        if commit:
            with transaction.atomic():
                user.save()
                UserProfile.objects.get_or_create(user=user)
                institution = self.cleaned_data['institution']
                Teacher.objects.create(
                    user=user,
                    employee_id=self._next_employee_id(institution),
                    employment_type=self.cleaned_data['employment_type'],
                    employment_status=Teacher.EmploymentStatus.ACTIVE,
                    joining_date=self.cleaned_data['joining_date'],
                    qualification=self.cleaned_data['qualification'],
                    specialization=self.cleaned_data.get('specialization') or '',
                    experience_years=self.cleaned_data.get('experience_years') or 0,
                    phone_number=self.cleaned_data['phone_number'],
                    emergency_contact=self.cleaned_data.get('emergency_contact') or '',
                    address=self.cleaned_data['address'],
                )
                InstitutionMembership.objects.get_or_create(
                    institution=institution,
                    user=user,
                    defaults={'role': InstitutionMembership.MembershipRole.TEACHER},
                )
        return user

    @staticmethod
    def _institution_prefix(institution):
        return ''.join(char for char in institution.code.upper() if char.isalnum()) or 'SCH'

    def _next_employee_id(self, institution):
        prefix = self._institution_prefix(institution)[:14]
        base = f'{prefix}-T'
        existing_ids = Teacher.objects.filter(
            user__institution_memberships__institution=institution,
            employee_id__startswith=base,
        ).values_list('employee_id', flat=True)
        numbers = []
        for employee_id in existing_ids:
            suffix = employee_id[len(base):]
            if suffix.isdigit():
                numbers.append(int(suffix))
        number = (max(numbers) + 1) if numbers else 1

        while True:
            employee_id = f'{base}{number:03d}'[:20]
            if not Teacher.objects.filter(employee_id=employee_id).exists():
                return employee_id
            number += 1


class InstitutionRegistrationForm(UserCreationForm):
    institution_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    institution_code = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
    )
    institution_type = forms.ChoiceField(
        choices=Institution.InstitutionType.choices,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    country = forms.CharField(
        max_length=100,
        required=True,
        initial='Zambia',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    province = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    district = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    institution_address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
    institution_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
    )
    institution_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control'}),
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    phone_number = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'tel'}),
    )

    class Meta:
        model = User
        fields = (
            'institution_name', 'institution_code', 'institution_type', 'country',
            'province', 'district', 'institution_address', 'institution_phone',
            'institution_email', 'website', 'first_name', 'last_name', 'email',
            'phone_number', 'password1', 'password2'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'autocomplete': 'new-password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean_institution_code(self):
        code = ''.join(char for char in self.cleaned_data.get('institution_code', '').upper() if char.isalnum() or char == '-')
        if not code:
            raise ValidationError('Institution code is required.')
        if Institution.objects.filter(code__iexact=code).exists():
            raise ValidationError('An institution with this code already exists.')
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.user_type = User.UserType.ADMINISTRATOR
        user.phone_number = self.cleaned_data.get('phone_number') or ''

        if commit:
            with transaction.atomic():
                institution = Institution.objects.create(
                    name=self.cleaned_data['institution_name'],
                    code=self.cleaned_data['institution_code'],
                    institution_type=self.cleaned_data['institution_type'],
                    country=self.cleaned_data['country'],
                    province=self.cleaned_data.get('province') or '',
                    district=self.cleaned_data.get('district') or '',
                    address=self.cleaned_data.get('institution_address') or '',
                    phone_number=self.cleaned_data.get('institution_phone') or '',
                    email=self.cleaned_data.get('institution_email') or '',
                    website=self.cleaned_data.get('website') or '',
                    is_active=True,
                    status=Institution.Status.PENDING,
                )
                user.save()
                UserProfile.objects.get_or_create(user=user)
                InstitutionMembership.objects.create(
                    institution=institution,
                    user=user,
                    role=InstitutionMembership.MembershipRole.OWNER,
                )
                self.institution = institution
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'emergency_contact_name', 'emergency_contact_phone', 
            'emergency_contact_relationship', 'language_preference', 
            'timezone', 'bio', 'skills', 'certifications'
        ]
        widgets = {
            'skills': forms.Textarea(attrs={'rows': 3}),
            'certifications': forms.Textarea(attrs={'rows': 3}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput())
    new_password1 = forms.CharField(widget=forms.PasswordInput())
    new_password2 = forms.CharField(widget=forms.PasswordInput())
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError('Your old password was entered incorrectly.')
        return old_password
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        if password1 and password2:
            if password1 != password2:
                raise ValidationError("The two password fields didn't match.")
        return password2
    
    def save(self, commit=True):
        self.user.set_password(self.cleaned_data['new_password1'])
        if commit:
            self.user.save()
        return self.user


class PasswordResetForm(forms.Form):
    email = forms.EmailField()
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('No user found with this email address.')
        return email


class TwoFactorSetupForm(forms.Form):
    enable_2fa = forms.BooleanField(required=False)
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def save(self):
        if self.cleaned_data.get('enable_2fa'):
            # Generate 2FA secret and enable
            import secrets
            self.user.two_factor_secret = secrets.token_hex(16)
            self.user.two_factor_enabled = True
        else:
            self.user.two_factor_enabled = False
            self.user.two_factor_secret = None
        
        self.user.save()
        return self.user


class InstitutionProfileForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = [
            'institution_type', 'country', 'province', 'district',
            'address', 'phone_number', 'email', 'website',
        ]
        widgets = {
            'institution_type': forms.Select(attrs={'class': 'form-select'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'province': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
        }


class InstitutionSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, code or email',
        }),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All statuses')] + list(Institution.Status.choices),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class OnboardingAcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if name and AcademicYear.objects.filter(name__iexact=name).exists():
            raise ValidationError('An academic year with this name already exists.')
        return name


class OnboardingClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name', 'display_name', 'section', 'capacity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.TextInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, academic_year=None, **kwargs):
        self.academic_year = academic_year
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if name and Class.objects.filter(name__iexact=name).exists():
            raise ValidationError('A class with this name already exists.')
        return name

    def save(self, commit=True):
        class_obj = super().save(commit=False)
        if self.academic_year is not None:
            class_obj.academic_year = self.academic_year
        if commit:
            class_obj.save()
        return class_obj


class OnboardingFeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if name and FeeCategory.objects.filter(name__iexact=name).exists():
            raise ValidationError('A fee category with this name already exists.')
        return name


class OnboardingFeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['name', 'academic_year', 'class_obj', 'fee_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
            'fee_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, institution=None, **kwargs):
        super().__init__(*args, **kwargs)
        if institution is not None:
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(
                institution=institution,
            ).order_by('-start_date')
            self.fields['class_obj'].queryset = Class.objects.filter(
                academic_year__institution=institution,
            ).select_related('academic_year').order_by('display_name')
        else:
            self.fields['academic_year'].queryset = AcademicYear.objects.none()
            self.fields['class_obj'].queryset = Class.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        academic_year = cleaned_data.get('academic_year')
        class_obj = cleaned_data.get('class_obj')
        if academic_year and class_obj and class_obj.academic_year_id != academic_year.id:
            self.add_error('class_obj', 'Selected class does not belong to the selected academic year.')
        return cleaned_data
