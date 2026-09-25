from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Institution, InstitutionMembership, User
from students.models import AcademicYear, Class, Student
from .models import FeeCategory, FeeStructure, FeeStructureDetail, Payment, Receipt, ReceiptSequence, StudentFee
from .serializers import PaymentCreateSerializer
from .services import PaymentRecordingError, create_receipt_for_payment, record_payment
from .views import PaymentViewSet, StudentFeeListView
from .views import generate_summary_report, outstanding_fee_total


class FeeRegressionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.request_factory = RequestFactory()
        self.institution = Institution.objects.create(name='Finance School', code='FIN-SCHOOL')
        self.accountant = User.objects.create_user(
            email='accountant@example.com',
            password='password123',
            first_name='Fee',
            last_name='Officer',
            user_type=User.UserType.ACCOUNTANT,
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=self.accountant,
            role=InstitutionMembership.MembershipRole.ACCOUNTANT,
        )
        self.year = AcademicYear.objects.create(
            institution=self.institution,
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            name='G10A',
            display_name='Grade 10 A',
            academic_year=self.year,
            capacity=40,
        )
        user = User.objects.create_user(
            email='fee-student@example.com',
            password='password123',
            first_name='Fee',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.student = Student.objects.create(
            user=user,
            student_id='FS001',
            admission_number='ADM-FS001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        category = FeeCategory.objects.create(name='Tuition')
        structure = FeeStructure.objects.create(
            name='Annual Tuition',
            academic_year=self.year,
            class_obj=self.class_obj,
            fee_type=FeeStructure.FeeType.ANNUAL,
        )
        detail = FeeStructureDetail.objects.create(
            fee_structure=structure,
            fee_category=category,
            amount=Decimal('1000.00'),
            due_date=date.today(),
        )
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure_detail=detail,
            amount=Decimal('1000.00'),
            paid_amount=Decimal('250.00'),
            due_date=date.today(),
            payment_status=StudentFee.PaymentStatus.PARTIAL,
        )

    def test_outstanding_fee_total_uses_expression_not_model_property(self):
        self.assertEqual(outstanding_fee_total(StudentFee.objects.all()), Decimal('750'))

    def test_summary_report_filters_through_current_class_academic_year(self):
        summary = generate_summary_report(self.year, self.class_obj, None, None)

        self.assertEqual(summary['total_outstanding'], Decimal('750'))
        self.assertEqual(summary['total_collection'], Decimal('0'))
        self.assertEqual(summary['total_discounts'], Decimal('0'))

    def test_completed_payment_updates_fee_balance(self):
        serializer = PaymentCreateSerializer(
            data={
                'student': self.student.pk,
                'student_fee': self.student_fee.pk,
                'amount': '250.00',
                'payment_method': Payment.PaymentMethod.CASH,
                'payment_status': Payment.PaymentStatus.COMPLETED,
            },
            context={'request': self.request_for_accountant()},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        payment = serializer.save()
        self.student_fee.refresh_from_db()

        self.assertEqual(payment.received_by, self.accountant)
        self.assertEqual(self.student_fee.paid_amount, Decimal('500.00'))
        self.assertEqual(self.student_fee.payment_status, StudentFee.PaymentStatus.PARTIAL)
        self.assertTrue(Receipt.objects.filter(payment=payment).exists())

    def test_payment_cannot_exceed_outstanding_balance(self):
        serializer = PaymentCreateSerializer(
            data={
                'student': self.student.pk,
                'student_fee': self.student_fee.pk,
                'amount': '751.00',
                'payment_method': Payment.PaymentMethod.CASH,
                'payment_status': Payment.PaymentStatus.COMPLETED,
            },
            context={'request': self.request_for_accountant()},
        )

        self.assertFalse(serializer.is_valid())

    def test_payment_rejects_student_fee_mismatch(self):
        other_user = User.objects.create_user(
            email='other-fee-student@example.com',
            password='password123',
            first_name='Other',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        other_student = Student.objects.create(
            user=other_user,
            student_id='FS002',
            admission_number='ADM-FS002',
            gender=Student.Gender.MALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        serializer = PaymentCreateSerializer(
            data={
                'student': other_student.pk,
                'student_fee': self.student_fee.pk,
                'amount': '10.00',
                'payment_method': Payment.PaymentMethod.CASH,
                'payment_status': Payment.PaymentStatus.COMPLETED,
            },
            context={'request': self.request_for_accountant()},
        )

        self.assertFalse(serializer.is_valid())

    def test_record_payment_rechecks_balance_inside_transaction(self):
        with self.assertRaises(PaymentRecordingError):
            record_payment(
                student=self.student,
                student_fee=self.student_fee,
                amount=Decimal('751.00'),
                payment_method=Payment.PaymentMethod.CASH,
                payment_status=Payment.PaymentStatus.COMPLETED,
                received_by=self.accountant,
            )

        self.assertFalse(Payment.objects.exists())
        self.student_fee.refresh_from_db()
        self.assertEqual(self.student_fee.paid_amount, Decimal('250.00'))

    def test_web_payment_create_uses_transactional_service(self):
        self.client.force_login(self.accountant)

        response = self.client.post(reverse('fees:payment_create'), {
            'student': self.student.pk,
            'student_fee': self.student_fee.pk,
            'amount': '750.00',
            'payment_method': Payment.PaymentMethod.CASH,
            'payment_status': Payment.PaymentStatus.COMPLETED,
            'transaction_id': 'WEB-001',
            'reference_number': 'REF-001',
            'remarks': 'Paid at office',
        })

        self.assertEqual(response.status_code, 302)
        self.student_fee.refresh_from_db()
        payment = Payment.objects.get(transaction_id='WEB-001')
        self.assertEqual(payment.received_by, self.accountant)
        self.assertEqual(self.student_fee.paid_amount, Decimal('1000.00'))
        self.assertEqual(self.student_fee.payment_status, StudentFee.PaymentStatus.PAID)
        self.assertTrue(Receipt.objects.filter(payment=payment).exists())

    def test_receipt_generation_is_idempotent(self):
        payment = Payment.objects.create(
            student=self.student,
            student_fee=self.student_fee,
            amount=Decimal('100.00'),
            payment_method=Payment.PaymentMethod.CASH,
            payment_status=Payment.PaymentStatus.COMPLETED,
            received_by=self.accountant,
        )

        first = create_receipt_for_payment(payment)
        second = create_receipt_for_payment(payment)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Receipt.objects.filter(payment=payment).count(), 1)

    def test_receipt_sequence_generates_unique_numbers_per_year(self):
        first = ReceiptSequence.next_receipt_number()
        second = ReceiptSequence.next_receipt_number()

        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith('RCP'))
        self.assertTrue(second.endswith('000002'))

    def test_receipt_endpoint_is_idempotent(self):
        payment = Payment.objects.create(
            student=self.student,
            student_fee=self.student_fee,
            amount=Decimal('100.00'),
            payment_method=Payment.PaymentMethod.CASH,
            payment_status=Payment.PaymentStatus.COMPLETED,
            received_by=self.accountant,
        )
        request = self.factory.post(f'/api/v1/fees/api/payments/{payment.pk}/generate_receipt/')
        force_authenticate(request, user=self.accountant)
        view = PaymentViewSet.as_view({'post': 'generate_receipt'})

        first = view(request, pk=payment.pk)
        second = view(request, pk=payment.pk)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Receipt.objects.filter(payment=payment).count(), 1)

    def test_receipt_frontend_pages_render_for_accountant(self):
        payment = record_payment(
            student=self.student,
            student_fee=self.student_fee,
            amount=Decimal('100.00'),
            payment_method=Payment.PaymentMethod.CASH,
            payment_status=Payment.PaymentStatus.COMPLETED,
            received_by=self.accountant,
        )
        receipt = payment.receipt
        self.client.force_login(self.accountant)

        list_response = self.client.get(reverse('fees:receipt_list'))
        detail_response = self.client.get(reverse('fees:receipt_detail', args=[receipt.pk]))
        payment_response = self.client.get(reverse('fees:payment_detail', args=[payment.pk]))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, receipt.receipt_number)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Amount Paid')
        self.assertEqual(payment_response.status_code, 200)
        self.assertContains(payment_response, reverse('fees:receipt_detail', args=[receipt.pk]))

    def test_my_fees_page_renders_student_balance(self):
        self.client.force_login(self.student.user)

        response = self.client.get(reverse('fees:my_fees'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Fees')
        self.assertContains(response, 'Tuition')
        self.assertContains(response, '750')

    def request_for_accountant(self):
        request = self.factory.post('/api/v1/fees/api/payments/')
        request.user = self.accountant
        return request

    def test_web_student_fee_list_is_scoped_to_accountant_institution(self):
        other_institution = Institution.objects.create(name='Other Finance School', code='OTHER-FIN')
        other_year = AcademicYear.objects.create(
            institution=other_institution,
            name='2027',
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
        )
        other_class = Class.objects.create(
            name='G11B',
            display_name='Grade 11 B',
            academic_year=other_year,
            capacity=40,
        )
        other_user = User.objects.create_user(
            email='other-finance-student@example.com',
            password='password123',
            first_name='Other',
            last_name='Finance',
            user_type=User.UserType.STUDENT,
        )
        other_student = Student.objects.create(
            user=other_user,
            student_id='FS999',
            admission_number='ADM-FS999',
            gender=Student.Gender.MALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=other_class,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        other_category = FeeCategory.objects.create(name='Other Tuition')
        other_structure = FeeStructure.objects.create(
            name='Other Annual Tuition',
            academic_year=other_year,
            class_obj=other_class,
            fee_type=FeeStructure.FeeType.ANNUAL,
        )
        other_detail = FeeStructureDetail.objects.create(
            fee_structure=other_structure,
            fee_category=other_category,
            amount=Decimal('1000.00'),
            due_date=date.today(),
        )
        StudentFee.objects.create(
            student=other_student,
            fee_structure_detail=other_detail,
            amount=Decimal('1000.00'),
            due_date=date.today(),
            payment_status=StudentFee.PaymentStatus.PENDING,
        )

        request = self.request_factory.get('/fees/student-fees/')
        request.user = self.accountant
        view = StudentFeeListView()
        view.request = request

        returned_students = {fee.student.student_id for fee in view.get_queryset()}

        self.assertEqual(returned_students, {'FS001'})
