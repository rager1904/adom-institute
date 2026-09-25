from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Attendance, ClassAttendance, TeacherAttendance, LeaveRequest
from students.models import Student, Class
from teachers.models import Teacher


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['student', 'date', 'status', 'remarks']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter remarks if any'}),
        }
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError("Attendance cannot be marked for future dates.")
        return date


class BulkAttendanceForm(forms.Form):
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Class'
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        initial=timezone.now().date()
    )
    
    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError("Attendance cannot be marked for future dates.")
        return date


class StudentAttendanceForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    status = forms.ChoiceField(
        choices=Attendance.AttendanceStatus.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Remarks'})
    )


class ClassAttendanceForm(forms.ModelForm):
    class Meta:
        model = ClassAttendance
        fields = ['class_obj', 'date', 'total_students', 'present_count', 'absent_count', 'late_count']
        widgets = {
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_students': forms.NumberInput(attrs={'class': 'form-control'}),
            'present_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'absent_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'late_count': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        total_students = cleaned_data.get('total_students')
        present_count = cleaned_data.get('present_count')
        absent_count = cleaned_data.get('absent_count')
        late_count = cleaned_data.get('late_count')
        
        if all([total_students, present_count, absent_count, late_count]):
            total_marked = present_count + absent_count + late_count
            if total_marked != total_students:
                raise ValidationError(
                    f"Total marked students ({total_marked}) must equal total students ({total_students})"
                )
        
        return cleaned_data


class TeacherAttendanceForm(forms.ModelForm):
    class Meta:
        model = TeacherAttendance
        fields = ['teacher', 'date', 'status', 'check_in_time', 'check_out_time', 'remarks']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'check_in_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter remarks if any'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        check_in_time = cleaned_data.get('check_in_time')
        check_out_time = cleaned_data.get('check_out_time')
        
        if check_in_time and check_out_time and check_in_time >= check_out_time:
            raise ValidationError("Check-out time must be after check-in time.")
        
        return cleaned_data


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason', 'supporting_document']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Please provide a detailed reason for your leave request'}),
            'supporting_document': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("End date must be after start date.")
            
            if start_date < timezone.now().date():
                raise ValidationError("Start date cannot be in the past.")
        
        return cleaned_data


class LeaveApprovalForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter approval remarks'}),
        }


class AttendanceSearchForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(Attendance.AttendanceStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class LeaveRequestSearchForm(forms.Form):
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    leave_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(LeaveRequest.LeaveType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(LeaveRequest.LeaveStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
