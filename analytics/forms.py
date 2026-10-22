from django import forms
from .models import Report
from students.models import AcademicYear, Class
from teachers.models import Teacher
from accounts.models import User


class ReportGenerationForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['name', 'report_type', 'description', 'parameters', 'filters', 'report_format']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter report name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Report description'}),
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'report_format': forms.Select(attrs={'class': 'form-select'}),
            'parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'JSON parameters'}),
            'filters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'JSON filters'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The choices come from the model, so they are present as long as the
        # form is bound to that model.  Ensure nothing empties the selector.
        self.fields['report_type'].choices = [('', 'Select Report Type')] + [
            (value, label) for value, label in Report.ReportType.choices
        ]
        self.fields['report_format'].choices = [('', 'Select Format')] + [
            (value, label) for value, label in Report.ReportFormat.choices
        ]


class AnalyticsFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    academic_year = forms.ChoiceField(
        required=False,
        choices=[('', 'All Academic Years')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class_id = forms.ChoiceField(
        required=False,
        choices=[('', 'All Classes')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    teacher_id = forms.ChoiceField(
        required=False,
        choices=[('', 'All Teachers')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student_id = forms.ChoiceField(
        required=False,
        choices=[('', 'All Students')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    event_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Events')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        institution_ids = kwargs.pop('institution_ids', None)
        super().__init__(*args, **kwargs)
        # Populate choices from the database so the filters show the available
        # academic years and classes (F-36).
        years = AcademicYear.objects.filter(is_active=True).order_by('-start_date')
        if institution_ids is not None:
            id_list = list(institution_ids)
            years = years.filter(institution_id__in=id_list)
        self.fields['academic_year'].choices = [('', 'All Academic Years')] + [
            (str(year.id), year.name) for year in years
        ]
        classes = Class.objects.filter(is_active=True).select_related('academic_year').order_by('display_name')
        if institution_ids is not None:
            id_list = list(institution_ids)
            classes = classes.filter(academic_year__institution_id__in=id_list)
        self.fields['class_id'].choices = [('', 'All Classes')] + [
            (str(cls.id), str(cls)) for cls in classes
        ]
        teachers = Teacher.objects.filter(is_active=True).select_related('user').order_by('user__first_name')
        if institution_ids is not None:
            id_list = list(institution_ids)
            teachers = teachers.filter(institution_id__in=id_list)
        self.fields['teacher_id'].choices = [('', 'All Teachers')] + [
            (str(teacher.id), teacher.user.get_full_name()) for teacher in teachers
        ]


class ExportForm(forms.Form):
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    
    export_format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_summary = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    date_range = forms.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('quarter', 'This Quarter'),
            ('year', 'This Year'),
            ('custom', 'Custom Range'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class DashboardFilterForm(forms.Form):
    time_period = forms.ChoiceField(
        choices=[
            ('7d', 'Last 7 Days'),
            ('30d', 'Last 30 Days'),
            ('90d', 'Last 90 Days'),
            ('1y', 'Last Year'),
        ],
        initial='30d',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    academic_year = forms.ChoiceField(
        required=False,
        choices=[('', 'All Academic Years')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class_filter = forms.ChoiceField(
        required=False,
        choices=[('', 'All Classes')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        institution_ids = kwargs.pop('institution_ids', None)
        super().__init__(*args, **kwargs)
        years = AcademicYear.objects.filter(is_active=True).order_by('-start_date')
        if institution_ids is not None:
            id_list = list(institution_ids)
            years = years.filter(institution_id__in=id_list)
        self.fields['academic_year'].choices = [('', 'All Academic Years')] + [
            (str(year.id), year.name) for year in years
        ]
        classes = Class.objects.filter(is_active=True).select_related('academic_year').order_by('display_name')
        if institution_ids is not None:
            id_list = list(institution_ids)
            classes = classes.filter(academic_year__institution_id__in=id_list)
        self.fields['class_filter'].choices = [('', 'All Classes')] + [
            (str(cls.id), str(cls)) for cls in classes
        ]


class PerformanceComparisonForm(forms.Form):
    COMPARISON_TYPES = [
        ('student', 'Student Performance'),
        ('class', 'Class Performance'),
        ('teacher', 'Teacher Performance'),
        ('subject', 'Subject Performance'),
    ]
    
    comparison_type = forms.ChoiceField(
        choices=COMPARISON_TYPES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    metric = forms.ChoiceField(
        choices=[
            ('percentage', 'Percentage'),
            ('attendance', 'Attendance'),
            ('assignments', 'Assignment Completion'),
            ('fees', 'Fee Payment'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    period_1 = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    period_2 = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
