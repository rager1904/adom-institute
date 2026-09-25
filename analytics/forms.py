from django import forms
from .models import Report


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
        super().__init__(*args, **kwargs)
        # You can populate choices dynamically here
        # For example, from database queries


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
