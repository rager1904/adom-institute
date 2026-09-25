from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Institution, User
from students.models import AcademicYear, Class, Student
from teachers.models import Teacher


class RoleAccessControlTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(name='Access School', code='ACCESS')
        self.year = AcademicYear.objects.create(
            institution=self.institution,
            name='Access 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.class_obj = Class.objects.create(
            name='ACCESS-G10',
            display_name='Access Grade 10',
            academic_year=self.year,
            capacity=40,
        )
        self.teacher_user = User.objects.create_user(
            email='teacher-access@example.com',
            password='password123',
            first_name='Teacher',
            last_name='Access',
            user_type=User.UserType.TEACHER,
            is_staff=True,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='ACCESS-T001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date(2026, 1, 1),
            qualification='BEd',
            phone_number='260970000000',
            address='Lusaka',
        )
        self.accountant = User.objects.create_user(
            email='accountant-access@example.com',
            password='password123',
            first_name='Accountant',
            last_name='Access',
            user_type=User.UserType.ACCOUNTANT,
        )
        self.admin = User.objects.create_user(
            email='admin-access@example.com',
            password='password123',
            first_name='Admin',
            last_name='Access',
            user_type=User.UserType.ADMINISTRATOR,
        )
        self.student_user = User.objects.create_user(
            email='student-access@example.com',
            password='password123',
            first_name='Student',
            last_name='Access',
            user_type=User.UserType.STUDENT,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='ACCESS001',
            admission_number='ACCESS-ADM001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2026, 1, 2),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def assert_denied(self, url):
        response = self.client.get(url)
        self.assertIn(response.status_code, (302, 403))

    def test_staff_flagged_teacher_cannot_access_admin_or_finance_pages(self):
        self.client.force_login(self.teacher_user)
        denied_urls = [
            reverse('fees:dashboard'),
            reverse('fees:student_fee_list'),
            reverse('fees:payment_list'),
            reverse('fees:payment_create'),
            reverse('teachers:teacher_create'),
            reverse('analytics:dashboard'),
            reverse('analytics:report_create'),
            reverse('communication:communication_report'),
            reverse('library:book_create'),
            reverse('timetable:room_create'),
        ]

        for url in denied_urls:
            with self.subTest(url=url):
                self.assert_denied(url)

    def test_accountant_can_access_finance_but_not_admin_setup_pages(self):
        self.client.force_login(self.accountant)

        self.assertEqual(self.client.get(reverse('fees:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('fees:student_fee_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('fees:payment_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('fees:payment_create')).status_code, 200)
        self.assert_denied(reverse('teachers:teacher_create'))
        self.assert_denied(reverse('analytics:dashboard'))
        self.assert_denied(reverse('analytics:report_create'))
        self.assert_denied(reverse('library:book_create'))

    def test_student_can_use_self_service_but_not_finance_dashboard(self):
        self.client.force_login(self.student_user)

        self.assertEqual(self.client.get(reverse('fees:student_fee_list')).status_code, 200)
        self.assert_denied(reverse('fees:dashboard'))
        self.assert_denied(reverse('teachers:teacher_create'))
        self.assert_denied(reverse('analytics:report_create'))

    def test_administrator_can_access_admin_and_finance_pages(self):
        self.client.force_login(self.admin)

        allowed_urls = [
            reverse('fees:dashboard'),
            reverse('teachers:teacher_create'),
            reverse('analytics:dashboard'),
            reverse('analytics:report_create'),
            reverse('communication:communication_report'),
            reverse('library:book_create'),
            reverse('timetable:room_create'),
        ]

        for url in allowed_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
