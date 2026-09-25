from rest_framework import serializers
from decimal import Decimal
from .models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee, 
    Payment, Receipt, FeeDiscount, StudentFeeDiscount
)
from .services import PaymentRecordingError, record_payment
from students.models import Student, Class, AcademicYear


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Student
        fields = ['id', 'full_name', 'student_id', 'current_class']


class ClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = ['id', 'name', 'section']


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date']


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FeeStructureSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    
    class Meta:
        model = FeeStructure
        fields = [
            'id', 'name', 'academic_year', 'academic_year_name', 'class_obj', 'class_name',
            'fee_type', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class FeeStructureDetailSerializer(serializers.ModelSerializer):
    fee_structure_name = serializers.CharField(source='fee_structure.name', read_only=True)
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)
    
    class Meta:
        model = FeeStructureDetail
        fields = [
            'id', 'fee_structure', 'fee_structure_name', 'fee_category', 'fee_category_name',
            'amount', 'is_optional', 'due_date', 'created_at'
        ]
        read_only_fields = ['created_at']


class StudentFeeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    fee_category_name = serializers.CharField(source='fee_structure_detail.fee_category.name', read_only=True)
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = StudentFee
        fields = [
            'id', 'student', 'student_name', 'fee_structure_detail', 'fee_category_name',
            'amount', 'paid_amount', 'balance_amount', 'due_date', 'payment_status',
            'is_paid', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['paid_amount', 'balance_amount', 'is_paid', 'is_overdue', 'created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    received_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'student', 'student_name', 'student_fee', 'amount', 'payment_method',
            'payment_status', 'transaction_id', 'reference_number', 'payment_date',
            'received_by', 'received_by_name', 'remarks', 'created_at', 'updated_at'
        ]
        read_only_fields = ['payment_date', 'created_at', 'updated_at']

    def get_received_by_name(self, obj):
        return obj.received_by.get_full_name() if obj.received_by else ''


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'student', 'student_fee', 'amount', 'payment_method', 'payment_status',
            'transaction_id', 'reference_number', 'remarks'
        ]

    def validate(self, attrs):
        student = attrs.get('student')
        student_fee = attrs.get('student_fee')
        amount = attrs.get('amount')

        if student_fee and student and student_fee.student_id != student.id:
            raise serializers.ValidationError('Student fee does not belong to the selected student.')
        if amount is not None and amount <= 0:
            raise serializers.ValidationError('Payment amount must be greater than zero.')
        if (
            amount is not None
            and student_fee
            and attrs.get('payment_status', Payment.PaymentStatus.PENDING) == Payment.PaymentStatus.COMPLETED
            and Decimal(amount) > student_fee.balance_amount
        ):
            raise serializers.ValidationError('Payment amount cannot exceed outstanding balance.')
        return attrs
    
    def create(self, validated_data):
        try:
            return record_payment(
                received_by=self.context['request'].user,
                **validated_data,
            )
        except PaymentRecordingError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            'id', 'payment', 'receipt_number', 'receipt_date', 'student_name',
            'class_name', 'fee_category', 'amount_paid', 'payment_method',
            'school_name', 'school_address', 'school_phone', 'pdf_file',
            'created_at'
        ]
        read_only_fields = ['receipt_number', 'receipt_date', 'created_at']


class FeeDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeDiscount
        fields = [
            'id', 'name', 'discount_type', 'discount_value', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class StudentFeeDiscountSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    discount_name = serializers.CharField(source='fee_discount.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = StudentFeeDiscount
        fields = [
            'id', 'student', 'student_name', 'fee_discount', 'discount_name',
            'student_fee', 'discount_amount', 'reason', 'approved_by',
            'approved_by_name', 'approved_at', 'created_at'
        ]
        read_only_fields = ['approved_at', 'created_at']


class StudentFeeDiscountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentFeeDiscount
        fields = ['student', 'fee_discount', 'student_fee', 'discount_amount', 'reason']
    
    def create(self, validated_data):
        # Set approved_by to current user
        validated_data['approved_by'] = self.context['request'].user
        return super().create(validated_data)


# Summary and Report Serializers
class FeeCollectionSummarySerializer(serializers.Serializer):
    total_collection = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_payments = serializers.IntegerField()
    pending_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    period = serializers.CharField()


class OutstandingFeeSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    student_name = serializers.CharField()
    class_name = serializers.CharField()
    total_outstanding = serializers.DecimalField(max_digits=10, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    due_date = serializers.DateField()


class FeeReportSerializer(serializers.Serializer):
    report_type = serializers.CharField()
    period = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    collected_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    collection_percentage = serializers.FloatField()
    data = serializers.ListField()


# Bulk Operations Serializers
class BulkFeeGenerationSerializer(serializers.Serializer):
    fee_structure = serializers.IntegerField()
    student_ids = serializers.ListField(child=serializers.IntegerField())
    due_date = serializers.DateField()
    
    def validate_fee_structure(self, value):
        try:
            FeeStructure.objects.get(id=value, is_active=True)
        except FeeStructure.DoesNotExist:
            raise serializers.ValidationError("Invalid fee structure.")
        return value


class BulkPaymentSerializer(serializers.Serializer):
    student_fee_ids = serializers.ListField(child=serializers.IntegerField())
    payment_method = serializers.CharField()
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)
    
    def validate_student_fee_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one student fee must be selected.")
        return value
