from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee, 
    Payment, Receipt, FeeDiscount, StudentFeeDiscount
)
from students.models import Student, Class, AcademicYear


class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FeeStructureForm(forms.ModelForm):
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


class FeeStructureDetailForm(forms.ModelForm):
    class Meta:
        model = FeeStructureDetail
        fields = ['fee_structure', 'fee_category', 'amount', 'is_optional', 'due_date']
        widgets = {
            'fee_structure': forms.Select(attrs={'class': 'form-select'}),
            'fee_category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class StudentFeeForm(forms.ModelForm):
    class Meta:
        model = StudentFee
        fields = ['student', 'fee_structure_detail', 'amount', 'due_date', 'payment_status']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'fee_structure_detail': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past.")
        return due_date


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['student', 'student_fee', 'amount', 'payment_method', 'payment_status', 
                 'transaction_id', 'reference_number', 'remarks']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'student_fee': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_status': forms.Select(attrs={'class': 'form-select'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        student_fee = self.cleaned_data.get('student_fee')
        
        if amount and student_fee:
            if amount > student_fee.balance_amount:
                raise ValidationError(f"Payment amount cannot exceed balance amount (₹{student_fee.balance_amount})")
        
        return amount


class FeeDiscountForm(forms.ModelForm):
    class Meta:
        model = FeeDiscount
        fields = ['name', 'discount_type', 'discount_value', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'discount_type': forms.Select(attrs={'class': 'form-select'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_discount_value(self):
        discount_value = self.cleaned_data.get('discount_value')
        discount_type = self.cleaned_data.get('discount_type')
        
        if discount_value and discount_value <= 0:
            raise ValidationError("Discount value must be greater than zero.")
        
        if discount_type == 'percentage' and discount_value > 100:
            raise ValidationError("Percentage discount cannot exceed 100%.")
        
        return discount_value


class StudentFeeDiscountForm(forms.ModelForm):
    class Meta:
        model = StudentFeeDiscount
        fields = ['student', 'fee_discount', 'student_fee', 'discount_amount', 'reason']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'fee_discount': forms.Select(attrs={'class': 'form-select'}),
            'student_fee': forms.Select(attrs={'class': 'form-select'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean_discount_amount(self):
        discount_amount = self.cleaned_data.get('discount_amount')
        student_fee = self.cleaned_data.get('student_fee')
        
        if discount_amount and student_fee:
            if discount_amount > student_fee.balance_amount:
                raise ValidationError(f"Discount amount cannot exceed balance amount (₹{student_fee.balance_amount})")
        
        return discount_amount


# Search and Filter Forms
class StudentFeeSearchForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    fee_category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(StudentFee.PaymentStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    due_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    due_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class PaymentSearchForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'All Methods')] + list(Payment.PaymentMethod.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(Payment.PaymentStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    payment_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class FeeReportForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    class_obj = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    fee_category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    report_type = forms.ChoiceField(
        choices=[
            ('collection', 'Fee Collection Report'),
            ('outstanding', 'Outstanding Fees Report'),
            ('discount', 'Discount Report'),
            ('summary', 'Summary Report')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )


# Bulk Operations Forms
class BulkFeeGenerationForm(forms.Form):
    fee_structure = forms.ModelChoiceField(
        queryset=FeeStructure.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past.")
        return due_date


class BulkPaymentForm(forms.Form):
    student_fees = forms.ModelMultipleChoiceField(
        queryset=StudentFee.objects.filter(payment_status__in=['pending', 'partial']),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    payment_method = forms.ChoiceField(
        choices=Payment.PaymentMethod.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    transaction_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
