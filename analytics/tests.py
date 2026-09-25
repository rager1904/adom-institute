from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from students.models import AcademicYear, Class, Student
from .models import StudentPerformance


class AnalyticsFrontendTests(TestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            email='analytics.student@example.com',
            password='pass12345',
            first_name='Ana',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.other_user = User.objects.create_user(
            email='analytics.other@example.com',
            password='pass12345',
            first_name='Other',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.academic_year = AcademicYear.objects.create(
            name='Analytics Year',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            name='ANA-8A',
            display_name='Analytics Grade 8A',
            academic_year=self.academic_year,
            capacity=40,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='ANA001',
            admission_number='ADM-ANA001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2012, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2024, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.other_student = Student.objects.create(
            user=self.other_user,
            student_id='ANA002',
            admission_number='ADM-ANA002',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2012, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2024, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def test_my_analytics_shows_only_current_student_performance(self):
        StudentPerformance.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            class_obj=self.class_obj,
            total_subjects=6,
            total_marks=Decimal('600.00'),
            obtained_marks=Decimal('510.00'),
            percentage=Decimal('85.00'),
            grade='A',
            total_days=100,
            present_days=92,
            attendance_percentage=Decimal('92.00'),
            total_assignments=20,
            submitted_assignments=18,
            assignment_completion_rate=Decimal('90.00'),
            total_fees=Decimal('1000.00'),
            paid_fees=Decimal('800.00'),
            fee_payment_rate=Decimal('80.00'),
            rank_in_class=2,
            class_average=Decimal('72.00'),
        )
        StudentPerformance.objects.create(
            student=self.other_student,
            academic_year=self.academic_year,
            class_obj=self.class_obj,
            total_subjects=6,
            total_marks=Decimal('600.00'),
            obtained_marks=Decimal('300.00'),
            percentage=Decimal('50.00'),
            grade='C',
        )

        self.client.force_login(self.student_user)
        response = self.client.get(reverse('analytics:my_analytics'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Student')
        self.assertContains(response, '85.00%')
        self.assertNotContains(response, 'Other Student')
