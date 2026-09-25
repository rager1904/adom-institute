from datetime import date

from django.test import TestCase
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Institution, InstitutionMembership, User
from academics.models import Assignment, Exam, ExamSubject, ExamType
from teachers.models import Subject, Teacher
from .models import AcademicYear, Class, Parent, Student
from .views import StudentDetailView, StudentListView
from .views import StudentViewSet


class StudentTenantAuthorizationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.request_factory = RequestFactory()
        self.institution_a = Institution.objects.create(name='Institution A', code='INST-A')
        self.institution_b = Institution.objects.create(name='Institution B', code='INST-B')
        self.admin_a = User.objects.create_user(
            email='admin-a@example.com',
            password='password123',
            first_name='Admin',
            last_name='A',
            user_type=User.UserType.ADMINISTRATOR,
        )
        InstitutionMembership.objects.create(
            institution=self.institution_a,
            user=self.admin_a,
            role=InstitutionMembership.MembershipRole.ADMINISTRATOR,
        )
        self.class_a = self.create_class(self.institution_a, '2026-A', 'A-10')
        self.class_b = self.create_class(self.institution_b, '2026-B', 'B-10')
        self.student_a = self.create_student('student-a@example.com', 'SA001', self.class_a)
        self.student_b = self.create_student('student-b@example.com', 'SB001', self.class_b)
        self.parent_user = User.objects.create_user(
            email='parent-a@example.com',
            password='password123',
            first_name='Parent',
            last_name='A',
            user_type=User.UserType.PARENT,
        )
        InstitutionMembership.objects.create(
            institution=self.institution_a,
            user=self.parent_user,
            role=InstitutionMembership.MembershipRole.PARENT,
        )
        Parent.objects.create(
            student=self.student_a,
            user=self.parent_user,
            relationship=Parent.Relationship.GUARDIAN,
            phone_number='260970000003',
            email='parent-a@example.com',
            is_primary_contact=True,
        )

    def create_class(self, institution, year_name, class_name):
        academic_year = AcademicYear.objects.create(
            institution=institution,
            name=year_name,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        return Class.objects.create(
            name=class_name,
            display_name=f'Class {class_name}',
            academic_year=academic_year,
            capacity=40,
        )

    def create_student(self, email, student_id, class_obj):
        user = User.objects.create_user(
            email=email,
            password='password123',
            first_name='Student',
            last_name=student_id,
            user_type=User.UserType.STUDENT,
        )
        InstitutionMembership.objects.create(
            institution=class_obj.academic_year.institution,
            user=user,
            role=InstitutionMembership.MembershipRole.STUDENT,
        )
        return Student.objects.create(
            user=user,
            student_id=student_id,
            admission_number=f'ADM-{student_id}',
            gender=Student.Gender.MALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def list_students_for(self, user):
        request = self.factory.get('/api/v1/students/api/students/')
        force_authenticate(request, user=user)
        return StudentViewSet.as_view({'get': 'list'})(request)

    def web_request_for(self, user):
        request = self.request_factory.get('/students/students/')
        request.user = user
        return request

    def test_institution_admin_only_sees_students_in_their_institution(self):
        response = self.list_students_for(self.admin_a)

        self.assertEqual(response.status_code, 200)
        returned_ids = {item['student_id'] for item in response.data['results']}
        self.assertEqual(returned_ids, {'SA001'})

    def test_parent_only_sees_their_child(self):
        response = self.list_students_for(self.parent_user)

        self.assertEqual(response.status_code, 200)
        returned_ids = {item['student_id'] for item in response.data['results']}
        self.assertEqual(returned_ids, {'SA001'})

    def test_parent_cannot_create_student_records(self):
        request = self.factory.post(
            '/api/v1/students/api/students/',
            {
                'first_name': 'Unauthorized',
                'last_name': 'Student',
                'email': 'unauthorized-student@example.com',
                'student_id': 'UN001',
                'admission_number': 'ADM-UN001',
                'gender': Student.Gender.MALE,
                'date_of_birth': '2010-01-01',
                'address': 'Lusaka',
                'current_class': self.class_a.pk,
                'admission_date': '2026-06-13',
                'admission_status': Student.AdmissionStatus.PENDING,
                'is_active': True,
            },
            format='json',
        )
        force_authenticate(request, user=self.parent_user)
        response = StudentViewSet.as_view({'post': 'create'})(request)

        self.assertEqual(response.status_code, 403)

    def test_institution_admin_can_create_student_and_membership(self):
        request = self.factory.post(
            '/api/v1/students/api/students/',
            {
                'first_name': 'New',
                'last_name': 'Student',
                'email': 'new-student@example.com',
                'student_id': 'NS001',
                'admission_number': 'ADM-NS001',
                'gender': Student.Gender.FEMALE,
                'date_of_birth': '2010-01-01',
                'address': 'Lusaka',
                'current_class': self.class_a.pk,
                'admission_date': '2026-06-13',
                'admission_status': Student.AdmissionStatus.PENDING,
                'is_active': True,
            },
            format='json',
        )
        force_authenticate(request, user=self.admin_a)
        response = StudentViewSet.as_view({'post': 'create'})(request)

        self.assertEqual(response.status_code, 201)
        created = Student.objects.get(student_id='NS001')
        self.assertTrue(
            InstitutionMembership.objects.filter(
                institution=self.institution_a,
                user=created.user,
                role=InstitutionMembership.MembershipRole.STUDENT,
            ).exists()
        )

    def test_institution_admin_cannot_create_student_in_another_institution(self):
        request = self.factory.post(
            '/api/v1/students/api/students/',
            {
                'first_name': 'Cross',
                'last_name': 'Tenant',
                'email': 'cross-tenant@example.com',
                'student_id': 'CT001',
                'admission_number': 'ADM-CT001',
                'gender': Student.Gender.FEMALE,
                'date_of_birth': '2010-01-01',
                'address': 'Lusaka',
                'current_class': self.class_b.pk,
                'admission_date': '2026-06-13',
                'admission_status': Student.AdmissionStatus.PENDING,
                'is_active': True,
            },
            format='json',
        )
        force_authenticate(request, user=self.admin_a)
        response = StudentViewSet.as_view({'post': 'create'})(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Student.objects.filter(student_id='CT001').exists())

    def test_web_student_list_is_scoped_to_institution(self):
        view = StudentListView()
        view.request = self.web_request_for(self.admin_a)

        returned_ids = {student.student_id for student in view.get_queryset()}

        self.assertEqual(returned_ids, {'SA001'})

    def test_web_student_detail_hides_cross_institution_student(self):
        view = StudentDetailView()
        view.request = self.web_request_for(self.admin_a)

        self.assertFalse(view.get_queryset().filter(pk=self.student_b.pk).exists())

    def test_student_portal_shows_only_current_student_learning_data(self):
        subject = Subject.objects.create(name='Portal Mathematics', code='PORT-MATH')
        exams_start = timezone.localdate() + timezone.timedelta(days=7)
        teacher = self.create_teacher('portal-teacher@example.com', 'PORT-T001')
        Assignment.objects.create(
            title='Visible Portal Assignment',
            description='Visible assignment',
            subject=subject,
            class_obj=self.class_a,
            teacher=teacher,
            due_date=timezone.now() + timezone.timedelta(days=3),
            max_marks=100,
        )
        Assignment.objects.create(
            title='Hidden Portal Assignment',
            description='Hidden assignment',
            subject=subject,
            class_obj=self.class_b,
            teacher=teacher,
            due_date=timezone.now() + timezone.timedelta(days=3),
            max_marks=100,
        )
        exam_type = ExamType.objects.create(name='Portal Exam', weightage=100)
        visible_exam = Exam.objects.create(
            name='Visible Portal Exam',
            exam_type=exam_type,
            academic_year=self.class_a.academic_year,
            class_obj=self.class_a,
            start_date=exams_start,
            end_date=exams_start + timezone.timedelta(days=1),
            total_marks=100,
            passing_marks=40,
        )
        hidden_exam = Exam.objects.create(
            name='Hidden Portal Exam',
            exam_type=exam_type,
            academic_year=self.class_b.academic_year,
            class_obj=self.class_b,
            start_date=exams_start,
            end_date=exams_start + timezone.timedelta(days=1),
            total_marks=100,
            passing_marks=40,
        )
        ExamSubject.objects.create(
            exam=visible_exam,
            subject=subject,
            max_marks=100,
            passing_marks=40,
            exam_date=exams_start,
            duration=90,
        )
        ExamSubject.objects.create(
            exam=hidden_exam,
            subject=subject,
            max_marks=100,
            passing_marks=40,
            exam_date=exams_start,
            duration=90,
        )

        self.client.force_login(self.student_a.user)
        response = self.client.get(reverse('students:student_portal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Portal')
        self.assertContains(response, 'Visible Portal Assignment')
        self.assertContains(response, 'Visible Portal Exam')
        self.assertNotContains(response, 'Hidden Portal Assignment')
        self.assertNotContains(response, 'Hidden Portal Exam')

    def test_parent_portal_uses_my_children_label_and_hides_unlinked_students(self):
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse('students:student_portal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Children')
        self.assertContains(response, self.student_a.student_id)
        self.assertNotContains(response, self.student_b.student_id)

    def create_teacher(self, email, employee_id):
        user = User.objects.create_user(
            email=email,
            password='password123',
            first_name='Portal',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        return Teacher.objects.create(
            user=user,
            employee_id=employee_id,
            employment_type=Teacher.EmploymentType.FULL_TIME,
            employment_status=Teacher.EmploymentStatus.ACTIVE,
            joining_date=date(2025, 1, 1),
            qualification='BEd',
            specialization='Mathematics',
            phone_number='260970000009',
            address='Lusaka',
        )
