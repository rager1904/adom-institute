from decimal import Decimal

from django.db import transaction

from .models import Payment, Receipt, ReceiptSequence, StudentFee


class PaymentRecordingError(ValueError):
    pass


def update_student_fee_status(student_fee):
    if student_fee.paid_amount <= 0:
        student_fee.payment_status = StudentFee.PaymentStatus.PENDING
    elif student_fee.paid_amount >= student_fee.amount:
        student_fee.payment_status = StudentFee.PaymentStatus.PAID
    else:
        student_fee.payment_status = StudentFee.PaymentStatus.PARTIAL
    student_fee.save(update_fields=['paid_amount', 'payment_status', 'updated_at'])


@transaction.atomic
def record_payment(*, student, student_fee, amount, payment_method, payment_status, received_by=None,
                   transaction_id='', reference_number='', remarks='', issue_receipt=True):
    locked_fee = StudentFee.objects.select_for_update().select_related('student').get(pk=student_fee.pk)
    if locked_fee.student_id != student.id:
        raise PaymentRecordingError('Student fee does not belong to the selected student.')

    amount = Decimal(amount)
    if amount <= 0:
        raise PaymentRecordingError('Payment amount must be greater than zero.')

    if payment_status == Payment.PaymentStatus.COMPLETED and amount > locked_fee.balance_amount:
        raise PaymentRecordingError('Payment amount cannot exceed outstanding balance.')

    payment = Payment.objects.create(
        student=student,
        student_fee=locked_fee,
        amount=amount,
        payment_method=payment_method,
        payment_status=payment_status,
        transaction_id=transaction_id,
        reference_number=reference_number,
        remarks=remarks,
        received_by=received_by,
    )

    if payment.payment_status == Payment.PaymentStatus.COMPLETED:
        locked_fee.paid_amount += amount
        update_student_fee_status(locked_fee)
        if issue_receipt:
            create_receipt_for_payment(payment)

    return payment


@transaction.atomic
def create_receipt_for_payment(payment):
    payment = Payment.objects.select_related(
        'student__user',
        'student__current_class',
        'student_fee__fee_structure_detail__fee_category',
    ).select_for_update().get(pk=payment.pk)

    receipt = getattr(payment, 'receipt', None)
    if receipt:
        return receipt

    return Receipt.objects.create(
        payment=payment,
        receipt_number=ReceiptSequence.next_receipt_number(payment.payment_date),
        student_name=payment.student.user.get_full_name(),
        class_name=payment.student.current_class.name if payment.student.current_class else '',
        fee_category=payment.student_fee.fee_structure_detail.fee_category.name,
        amount_paid=payment.amount,
        payment_method=payment.get_payment_method_display(),
    )
