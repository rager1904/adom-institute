from django import forms
from django.core.exceptions import ValidationError
from .models import (
    ExamType, Exam, ExamSubject, Grade, StudentExamResult,
    Assignment, StudentAssignment
)


class ExamTypeForm(forms.ModelForm):
    class Meta:
        model = ExamType
        fields = ['name', 'description', 'weightage', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'weightage': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 0.01}),
        }
    
    def clean_weightage(self):
        weightage = self.cleaned_data.get('weightage')
        if weightage < 0 or weightage > 100:
            raise ValidationError('Weightage must be between 0 and 100')
        return weightage


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'exam_type', 'academic_year', 'class_obj', 'start_date', 'end_date', 'total_marks', 'passing_marks', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'total_marks': forms.NumberInput(attrs={'min': 1}),
            'passing_marks': forms.NumberInput(attrs={'min': 0}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        total_marks = cleaned_data.get('total_marks')
        passing_marks = cleaned_data.get('passing_marks')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError('Start date cannot be after end date')
        
        if total_marks and passing_marks and passing_marks > total_marks:
            raise ValidationError('Passing marks cannot be greater than total marks')
        
        return cleaned_data


class ExamSubjectForm(forms.ModelForm):
    class Meta:
        model = ExamSubject
        fields = ['exam', 'subject', 'max_marks', 'passing_marks', 'exam_date', 'duration']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
            'max_marks': forms.NumberInput(attrs={'min': 1}),
            'passing_marks': forms.NumberInput(attrs={'min': 0}),
            'duration': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Duration in minutes'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        max_marks = cleaned_data.get('max_marks')
        passing_marks = cleaned_data.get('passing_marks')
        exam = cleaned_data.get('exam')
        exam_date = cleaned_data.get('exam_date')
        
        if max_marks and passing_marks and passing_marks > max_marks:
            raise ValidationError('Passing marks cannot be greater than max marks')
        
        if exam and exam_date:
            if exam_date < exam.start_date or exam_date > exam.end_date:
                raise ValidationError('Exam date must be within the exam period')
        
        return cleaned_data


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['name', 'min_marks', 'max_marks', 'grade_point', 'description']
        widgets = {
            'min_marks': forms.NumberInput(attrs={'min': 0}),
            'max_marks': forms.NumberInput(attrs={'min': 0}),
            'grade_point': forms.NumberInput(attrs={'min': 0, 'max': 10, 'step': 0.01}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        min_marks = cleaned_data.get('min_marks')
        max_marks = cleaned_data.get('max_marks')
        grade_point = cleaned_data.get('grade_point')
        
        if min_marks and max_marks and min_marks >= max_marks:
            raise ValidationError('Min marks must be less than max marks')
        
        if grade_point and (grade_point < 0 or grade_point > 10):
            raise ValidationError('Grade point must be between 0 and 10')
        
        return cleaned_data


class StudentExamResultForm(forms.ModelForm):
    class Meta:
        model = StudentExamResult
        fields = ['student', 'exam_subject', 'marks_obtained', 'grade', 'remarks']
        widgets = {
            'marks_obtained': forms.NumberInput(attrs={'min': 0, 'step': 0.01}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        exam_subject = self.cleaned_data.get('exam_subject')
        
        if marks_obtained and exam_subject:
            if marks_obtained > exam_subject.max_marks:
                raise ValidationError(f'Marks cannot exceed {exam_subject.max_marks}')
            if marks_obtained < 0:
                raise ValidationError('Marks cannot be negative')
        
        return marks_obtained


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'subject', 'class_obj', 'due_date', 'max_marks', 'attachment', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Assignment title'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Assignment description'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'max_marks': forms.NumberInput(attrs={'min': 1}),
        }
    
    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date:
            from django.utils import timezone
            if due_date < timezone.now():
                raise ValidationError('Due date cannot be in the past')
        return due_date


class StudentAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentAssignment
        fields = ['assignment', 'submission_file', 'submission_text']
        widgets = {
            'submission_text': forms.Textarea(attrs={'rows': 6, 'placeholder': 'Enter your submission text here...'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        submission_file = cleaned_data.get('submission_file')
        submission_text = cleaned_data.get('submission_text')
        
        if not submission_file and not submission_text:
            raise ValidationError('Either submission file or text is required')
        
        return cleaned_data


class AssignmentGradingForm(forms.ModelForm):
    class Meta:
        model = StudentAssignment
        fields = ['marks_obtained', 'feedback']
        widgets = {
            'marks_obtained': forms.NumberInput(attrs={'min': 0, 'step': 0.01}),
            'feedback': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Provide feedback to the student...'}),
        }
    
    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        assignment = self.instance.assignment if self.instance else None
        
        if marks_obtained and assignment:
            if marks_obtained > assignment.max_marks:
                raise ValidationError(f'Marks cannot exceed {assignment.max_marks}')
            if marks_obtained < 0:
                raise ValidationError('Marks cannot be negative')
        
        return marks_obtained


class BulkGradeEntryForm(forms.Form):
    exam_subject = forms.ModelChoiceField(
        queryset=ExamSubject.objects.all(),
        label='Exam Subject',
        help_text='Select the exam subject for grade entry'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['exam_subject'].widget.attrs.update({'class': 'form-control'})


class ExamSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search exams...', 'class': 'form-control'})
    )
    exam_type = forms.ModelChoiceField(
        queryset=ExamType.objects.filter(is_active=True),
        required=False,
        empty_label="All Exam Types",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    academic_year = forms.ModelChoiceField(
        queryset=Exam.objects.values_list('academic_year', flat=True).distinct(),
        required=False,
        empty_label="All Academic Years",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class AssignmentSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search assignments...', 'class': 'form-control'})
    )
    subject = forms.ModelChoiceField(
        queryset=Assignment.objects.values_list('subject', flat=True).distinct(),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=[
            ('', 'All Status'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
