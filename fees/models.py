from django.db import models
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from students.models import Student, Class, AcademicYear
from accounts.models import User


class FeeCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fees_fee_category'
        verbose_name_plural = 'Fee Categories'
    
    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    class FeeType(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        QUARTERLY = 'quarterly', _('Quarterly')
        SEMESTER = 'semester', _('Semester')
        ANNUAL = 'annual', _('Annual')
        ONE_TIME = 'one_time', _('One Time')
    
    name = models.CharField(max_length=200)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='fee_structures')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='fee_structures')
    fee_type = models.CharField(max_length=20, choices=FeeType.choices)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fees_fee_structure'
        unique_together = ('name', 'academic_year', 'class_obj')
    
    def __str__(self):
        return f"{self.name} - {self.class_obj.name} ({self.academic_year.name})"


class FeeStructureDetail(models.Model):
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='fee_details')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='fee_structure_details')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_optional = models.BooleanField(default=False)
    due_date = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fees_fee_structure_detail'
        unique_together = ('fee_structure', 'fee_category')
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name='fees_detail_amount_ck',
            ),
        ]
    
    def __str__(self):
        return f"{self.fee_structure.name} - {self.fee_category.name} ({self.amount})"


class StudentFee(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PARTIAL = 'partial', _('Partial')
        PAID = 'paid', _('Paid')
        OVERDUE = 'overdue', _('Overdue')
        WAIVED = 'waived', _('Waived')
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_fees')
    fee_structure_detail = models.ForeignKey(FeeStructureDetail, on_delete=models.CASCADE, related_name='student_fees')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fees_student_fee'
        unique_together = ('student', 'fee_structure_detail')
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name='fees_student_amount_ck',
            ),
            models.CheckConstraint(
                check=models.Q(paid_amount__gte=0),
                name='fees_student_paid_ck',
            ),
            models.CheckConstraint(
                check=models.Q(paid_amount__lte=models.F('amount')),
                name='fees_student_balance_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['payment_status', 'due_date'], name='fees_status_due_idx'),
            models.Index(fields=['student', 'payment_status'], name='fees_student_status_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.fee_structure_detail.fee_category.name}"
    
    @property
    def balance_amount(self):
        return self.amount - self.paid_amount
    
    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.due_date < timezone.now().date() and not self.is_paid


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        CHEQUE = 'cheque', _('Cheque')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        ONLINE = 'online', _('Online Payment')
        CARD = 'card', _('Card Payment')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED = 'refunded', _('Refunded')
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='received_payments')
    remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fees_payment'
        ordering = ['-payment_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name='fees_payment_amount_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['student', 'payment_status', 'payment_date'], name='fees_payment_student_idx'),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.amount} ({self.get_payment_method_display()})"


class Receipt(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    receipt_number = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateTimeField(auto_now_add=True)
    
    # Receipt details
    student_name = models.CharField(max_length=200)
    class_name = models.CharField(max_length=100)
    fee_category = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    
    # School information
    school_name = models.CharField(max_length=200, default='ADOM Institute')
    school_address = models.TextField(default='School Address')
    school_phone = models.CharField(max_length=20, default='+1234567890')
    
    # Generated PDF
    pdf_file = models.FileField(upload_to='receipts/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fees_receipt'
        ordering = ['-receipt_date']
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.student_name}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = ReceiptSequence.next_receipt_number()
        
        super().save(*args, **kwargs)


class ReceiptSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fees_receipt_sequence'

    def __str__(self):
        return f'{self.year}: {self.last_number}'

    @classmethod
    def next_receipt_number(cls, receipt_date=None):
        receipt_date = receipt_date or timezone.now()
        year = receipt_date.year
        with transaction.atomic():
            sequence, _ = cls.objects.select_for_update().get_or_create(year=year)
            sequence.last_number += 1
            sequence.save(update_fields=['last_number', 'updated_at'])
            return f'RCP{year}{sequence.last_number:06d}'


class FeeDiscount(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', _('Percentage')
        FIXED_AMOUNT = 'fixed_amount', _('Fixed Amount')
    
    name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fees_fee_discount'
        constraints = [
            models.CheckConstraint(
                check=models.Q(discount_value__gte=0),
                name='fees_discount_value_ck',
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_discount_type_display()})"


class StudentFeeDiscount(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_discounts')
    fee_discount = models.ForeignKey(FeeDiscount, on_delete=models.CASCADE, related_name='student_discounts')
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='discounts')
    
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_discounts')
    approved_at = models.DateTimeField(auto_now_add=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fees_student_fee_discount'
        unique_together = ('student', 'fee_discount', 'student_fee')
        constraints = [
            models.CheckConstraint(
                check=models.Q(discount_amount__gte=0),
                name='fees_student_disc_ck',
            ),
        ]
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.fee_discount.name}"
