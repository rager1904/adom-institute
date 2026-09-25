from datetime import date, time
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from academics.models import Exam, ExamType
from analytics.models import StudentPerformance
from attendance.models import LeaveRequest
from accounts.models import User
from fees.models import FeeCategory, FeeStructure, FeeStructureDetail, Payment, StudentFee
from students.models import AcademicYear, Class, Student
from timetable.models import TimeSlot


class DatabaseIntegrityConstraintTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            name='Integrity 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.class_obj = Class.objects.create(
            name='INT-G10',
            display_name='Integrity Grade 10',
            academic_year=self.year,
            capacity=40,
        )
        self.student_user = User.objects.create_user(
            email='integrity-student@example.com',
            password='password123',
            first_name='Integrity',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='INT001',
            admission_number='ADM-INT001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2026, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def assert_integrity_error(self, create_callable):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_callable()

    def test_academic_year_requires_end_date_after_start_date(self):
        self.assert_integrity_error(
            lambda: AcademicYear.objects.create(
                name='Invalid Year',
                start_date=date(2026, 12, 31),
                end_date=date(2026, 1, 1),
            )
        )

    def test_student_admission_cannot_precede_birth_date(self):
        user = User.objects.create_user(
            email='invalid-admission@example.com',
            password='password123',
            first_name='Invalid',
            last_name='Admission',
            user_type=User.UserType.STUDENT,
        )

        self.assert_integrity_error(
            lambda: Student.objects.create(
                user=user,
                student_id='INT002',
                admission_number='ADM-INT002',
                gender=Student.Gender.MALE,
                date_of_birth=date(2010, 1, 1),
                address='Lusaka',
                current_class=self.class_obj,
                admission_date=date(2009, 1, 1),
                admission_status=Student.AdmissionStatus.PENDING,
            )
        )

    def test_exam_passing_marks_cannot_exceed_total_marks(self):
        exam_type = ExamType.objects.create(name='Integrity Exam')

        self.assert_integrity_error(
            lambda: Exam.objects.create(
                name='Invalid Exam',
                exam_type=exam_type,
                academic_year=self.year,
                class_obj=self.class_obj,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 5),
                total_marks=100,
                passing_marks=101,
            )
        )

    def test_student_fee_paid_amount_cannot_exceed_amount(self):
        category = FeeCategory.objects.create(name='Integrity Tuition')
        structure = FeeStructure.objects.create(
            name='Integrity Annual Tuition',
            academic_year=self.year,
            class_obj=self.class_obj,
            fee_type=FeeStructure.FeeType.ANNUAL,
        )
        detail = FeeStructureDetail.objects.create(
            fee_structure=structure,
            fee_category=category,
            amount=Decimal('100.00'),
            due_date=date(2026, 6, 1),
        )

        self.assert_integrity_error(
            lambda: StudentFee.objects.create(
                student=self.student,
                fee_structure_detail=detail,
                amount=Decimal('100.00'),
                paid_amount=Decimal('101.00'),
                due_date=date(2026, 6, 1),
            )
        )

    def test_payment_amount_must_be_positive(self):
        category = FeeCategory.objects.create(name='Integrity Lab Fee')
        structure = FeeStructure.objects.create(
            name='Integrity Lab Fees',
            academic_year=self.year,
            class_obj=self.class_obj,
            fee_type=FeeStructure.FeeType.ONE_TIME,
        )
        detail = FeeStructureDetail.objects.create(
            fee_structure=structure,
            fee_category=category,
            amount=Decimal('50.00'),
            due_date=date(2026, 6, 1),
        )
        student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure_detail=detail,
            amount=Decimal('50.00'),
            due_date=date(2026, 6, 1),
        )

        self.assert_integrity_error(
            lambda: Payment.objects.create(
                student=self.student,
                student_fee=student_fee,
                amount=Decimal('0.00'),
                payment_method=Payment.PaymentMethod.CASH,
            )
        )

    def test_leave_request_requires_exactly_one_owner(self):
        self.assert_integrity_error(
            lambda: LeaveRequest.objects.create(
                leave_type=LeaveRequest.LeaveType.SICK_LEAVE,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 3),
                reason='Invalid owner',
            )
        )

    def test_time_slot_requires_end_time_after_start_time(self):
        self.assert_integrity_error(
            lambda: TimeSlot.objects.create(
                day=TimeSlot.DayOfWeek.MONDAY,
                start_time=time(9, 0),
                end_time=time(8, 0),
                period_number=1,
            )
        )

    def test_student_performance_cannot_report_more_marks_than_total(self):
        self.assert_integrity_error(
            lambda: StudentPerformance.objects.create(
                student=self.student,
                academic_year=self.year,
                class_obj=self.class_obj,
                total_marks=Decimal('100.00'),
                obtained_marks=Decimal('101.00'),
            )
        )
