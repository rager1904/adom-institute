from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee, 
    Payment, Receipt, FeeDiscount, StudentFeeDiscount
)


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    ordering = ['name']


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'academic_year', 'class_obj', 'fee_type', 'is_active', 'created_at']
    list_filter = ['fee_type', 'is_active', 'academic_year', 'class_obj', 'created_at']
    search_fields = ['name', 'academic_year__name', 'class_obj__name']
    list_editable = ['is_active']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('academic_year', 'class_obj')


@admin.register(FeeStructureDetail)
class FeeStructureDetailAdmin(admin.ModelAdmin):
    list_display = ['fee_structure', 'fee_category', 'amount', 'is_optional', 'due_date']
    list_filter = ['is_optional', 'fee_category', 'fee_structure__fee_type']
    search_fields = ['fee_structure__name', 'fee_category__name']
    list_editable = ['amount', 'is_optional', 'due_date']
    ordering = ['fee_structure', 'fee_category']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('fee_structure', 'fee_category')


@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'fee_category', 'amount', 'paid_amount', 'balance_display', 
        'payment_status', 'due_date', 'is_overdue_display'
    ]
    list_filter = [
        'payment_status', 'due_date', 'fee_structure_detail__fee_category',
        'student__current_class', 'created_at'
    ]
    search_fields = [
        'student__user__first_name', 'student__user__last_name', 
        'student__student_id', 'fee_structure_detail__fee_category__name'
    ]
    list_editable = ['payment_status']
    readonly_fields = ['balance_amount', 'is_paid', 'is_overdue']
    ordering = ['-due_date']
    
    def fee_category(self, obj):
        return obj.fee_structure_detail.fee_category.name
    fee_category.short_description = 'Fee Category'
    
    def balance_display(self, obj):
        balance = obj.balance_amount
        if balance == 0:
            return format_html('<span style="color: green;">₹{}</span>', balance)
        elif balance < 0:
            return format_html('<span style="color: red;">₹{}</span>', balance)
        else:
            return format_html('<span style="color: orange;">₹{}</span>', balance)
    balance_display.short_description = 'Balance'
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">Overdue</span>')
        return format_html('<span style="color: green;">On Time</span>')
    is_overdue_display.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student__user', 'fee_structure_detail__fee_category', 'student__current_class'
        )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'amount', 'payment_method', 'payment_status', 
        'payment_date', 'received_by', 'transaction_id'
    ]
    list_filter = [
        'payment_method', 'payment_status', 'payment_date', 
        'received_by', 'created_at'
    ]
    search_fields = [
        'student__user__first_name', 'student__user__last_name',
        'transaction_id', 'reference_number'
    ]
    list_editable = ['payment_status']
    readonly_fields = ['payment_date']
    ordering = ['-payment_date']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student__user', 'received_by')


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        'receipt_number', 'student_name', 'class_name', 'fee_category',
        'amount_paid', 'payment_method', 'receipt_date'
    ]
    list_filter = ['receipt_date', 'payment_method', 'class_name']
    search_fields = ['receipt_number', 'student_name', 'fee_category']
    readonly_fields = ['receipt_number', 'receipt_date']
    ordering = ['-receipt_date']
    
    def has_add_permission(self, request):
        return False  # Receipts are auto-generated


@admin.register(FeeDiscount)
class FeeDiscountAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_type', 'discount_value', 'is_active', 'created_at']
    list_filter = ['discount_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    ordering = ['name']


@admin.register(StudentFeeDiscount)
class StudentFeeDiscountAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'fee_discount', 'student_fee', 'discount_amount', 
        'approved_by', 'approved_at'
    ]
    list_filter = ['approved_at', 'fee_discount__discount_type', 'created_at']
    search_fields = [
        'student__user__first_name', 'student__user__last_name',
        'fee_discount__name', 'reason'
    ]
    readonly_fields = ['approved_at']
    ordering = ['-approved_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'student__user', 'fee_discount', 'approved_by'
        )


# Customize admin site
admin.site.site_header = "ADOM Institute - Fees"
admin.site.site_title = "ADOM Institute Fees"
admin.site.index_title = "Fees Management"
