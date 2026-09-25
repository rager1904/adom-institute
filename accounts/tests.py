from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from academics.models import Exam, ExamSubject, ExamType, Grade, StudentExamResult
from accounts.dashboard_services import build_dashboard_context
from .forms import InstitutionRegistrationForm, TeacherRegistrationForm, UserRegistrationForm
from .models import Institution, InstitutionMembership, User
from students.models import AcademicYear, Class, Student
from teachers.models import Subject, Teacher, TeacherSubject
from timetable.models import ClassSchedule, Room, TimeSlot


class UserRegistrationFormTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(
            name='Signup School',
            code='SIGNUP',
        )
        self.year = AcademicYear.objects.create(
            institution=self.institution,
            name='Signup 2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            name='SIGNUP-G10',
            display_name='Signup Grade 10',
            academic_year=self.year,
            capacity=40,
        )
        existing_user = User.objects.create_user(
            email='existing.student@example.com',
            password='SecurePass123!',
            first_name='Existing',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        Student.objects.create(
            user=existing_user,
            student_id='SIGNUP001',
            admission_number='ADM-SIGNUP001',
            roll_number='001',
            gender=Student.Gender.FEMALE,
            date_of_birth='2010-01-01',
            phone_number='260970000000',
            address='Lusaka',
            current_class=self.class_obj,
            admission_date='2026-01-01',
            admission_status=Student.AdmissionStatus.PENDING,
        )

    def valid_form_data(self, **overrides):
        data = {
            'email': 'new.student@example.com',
            'first_name': 'New',
            'last_name': 'Student',
            'institution': self.institution.pk,
            'current_class': self.class_obj.pk,
            'gender': Student.Gender.FEMALE,
            'phone_number': '260970000000',
            'date_of_birth': '2010-01-01',
            'address': 'Lusaka',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        }
        data.update(overrides)
        return data

    def test_signup_saves_student_user_type_profile_and_membership_role(self):
        form = UserRegistrationForm(data=self.valid_form_data())

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        user.refresh_from_db()
        self.assertEqual(user.user_type, User.UserType.STUDENT)
        self.assertEqual(user.phone_number, '260970000000')
        student = Student.objects.get(user=user)
        self.assertEqual(student.student_id, 'SIGNUP002')
        self.assertEqual(student.admission_number, 'ADM-SIGNUP002')
        self.assertEqual(student.current_class, self.class_obj)
        membership = InstitutionMembership.objects.get(user=user, institution=self.institution)
        self.assertEqual(membership.role, InstitutionMembership.MembershipRole.STUDENT)

    def test_signup_requires_school_selection(self):
        form = UserRegistrationForm(data=self.valid_form_data(institution=''))

        self.assertFalse(form.is_valid())
        self.assertIn('institution', form.errors)

    def test_register_view_creates_student_with_generated_identifiers(self):
        response = self.client.post(
            reverse('accounts:register'),
            self.valid_form_data(email='signed-up.student@example.com'),
        )

        self.assertRedirects(response, reverse('accounts:login'))
        user = User.objects.get(email='signed-up.student@example.com')
        self.assertEqual(user.user_type, User.UserType.STUDENT)
        student = Student.objects.get(user=user)
        self.assertEqual(student.student_id, 'SIGNUP002')
        self.assertEqual(student.admission_number, 'ADM-SIGNUP002')
        membership = InstitutionMembership.objects.get(user=user, institution=self.institution)
        self.assertEqual(membership.role, InstitutionMembership.MembershipRole.STUDENT)

    def test_student_dashboard_averages_exam_percentages_without_field_error(self):
        user = User.objects.create_user(
            email='dashboard.student@example.com',
            password='SecurePass123!',
            first_name='Dashboard',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        student = Student.objects.create(
            user=user,
            student_id='SIGNUP002',
            admission_number='ADM-SIGNUP002',
            roll_number='002',
            gender=Student.Gender.FEMALE,
            date_of_birth='2010-01-01',
            phone_number='260970000001',
            address='Lusaka',
            current_class=self.class_obj,
            admission_date='2026-01-01',
            admission_status=Student.AdmissionStatus.PENDING,
        )
        teacher_user = User.objects.create_user(
            email='dashboard.teacher@example.com',
            password='SecurePass123!',
            first_name='Dashboard',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            employee_id='SIGNUP-T001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date='2026-01-01',
            qualification='BEd',
            phone_number='260970000002',
            address='Lusaka',
        )
        exam_type = ExamType.objects.create(name='Midterm')
        exam = Exam.objects.create(
            name='Signup Midterm',
            exam_type=exam_type,
            academic_year=self.year,
            class_obj=self.class_obj,
            start_date='2026-06-01',
            end_date='2026-06-02',
            total_marks=100,
            passing_marks=50,
        )
        subject = Subject.objects.create(name='Signup Mathematics', code='SIGN-MATH')
        exam_subject = ExamSubject.objects.create(
            exam=exam,
            subject=subject,
            max_marks=100,
            passing_marks=50,
            exam_date='2026-06-01',
            duration=90,
        )
        grade = Grade.objects.create(
            name='Signup-A',
            min_marks=75,
            max_marks=100,
            grade_point=Decimal('4.00'),
        )
        StudentExamResult.objects.create(
            student=student,
            exam_subject=exam_subject,
            marks_obtained=Decimal('82.50'),
            grade=grade,
            created_by=teacher,
        )

        context = build_dashboard_context(user)

        self.assertEqual(context['role_label'], 'Student')
        self.assertEqual(context['stats'][0]['value'], '3.5')

    def test_teacher_register_view_creates_teacher_profile_and_membership(self):
        response = self.client.post(
            reverse('accounts:teacher_register'),
            {
                'email': 'new.teacher@example.com',
                'first_name': 'New',
                'last_name': 'Teacher',
                'institution': self.institution.pk,
                'employment_type': Teacher.EmploymentType.FULL_TIME,
                'joining_date': '2026-01-01',
                'qualification': 'BEd',
                'specialization': 'Mathematics',
                'experience_years': 3,
                'phone_number': '260970000003',
                'emergency_contact': '260970000004',
                'address': 'Lusaka',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
            },
        )

        self.assertRedirects(response, reverse('accounts:login'))
        user = User.objects.get(email='new.teacher@example.com')
        self.assertEqual(user.user_type, User.UserType.TEACHER)
        teacher = Teacher.objects.get(user=user)
        self.assertEqual(teacher.employee_id, 'SIGNUP-T001')
        membership = InstitutionMembership.objects.get(user=user, institution=self.institution)
        self.assertEqual(membership.role, InstitutionMembership.MembershipRole.TEACHER)

    def test_institution_register_view_creates_owner_admin_and_institution(self):
        response = self.client.post(
            reverse('accounts:institution_register'),
            {
                'institution_name': 'New Institution',
                'institution_code': 'new-inst',
                'institution_type': Institution.InstitutionType.SECONDARY_SCHOOL,
                'country': 'Zambia',
                'province': 'Lusaka',
                'district': 'Lusaka',
                'institution_address': 'Lusaka',
                'institution_phone': '260970000005',
                'institution_email': 'office@newinst.example.com',
                'website': 'https://newinst.example.com',
                'first_name': 'Owner',
                'last_name': 'Admin',
                'email': 'owner@newinst.example.com',
                'phone_number': '260970000006',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
            },
        )

        self.assertRedirects(response, reverse('accounts:login'))
        institution = Institution.objects.get(code='NEW-INST')
        self.assertEqual(institution.name, 'New Institution')
        user = User.objects.get(email='owner@newinst.example.com')
        self.assertEqual(user.user_type, User.UserType.ADMINISTRATOR)
        membership = InstitutionMembership.objects.get(user=user, institution=institution)
        self.assertEqual(membership.role, InstitutionMembership.MembershipRole.OWNER)

    def test_admin_can_place_student_in_class_from_frontend(self):
        admin = User.objects.create_user(
            email='placement.admin@example.com',
            password='SecurePass123!',
            first_name='Placement',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=admin,
            role=InstitutionMembership.MembershipRole.OWNER,
        )
        target_class = Class.objects.create(
            name='SIGNUP-G11',
            display_name='Signup Grade 11',
            academic_year=self.year,
            capacity=40,
        )
        student = Student.objects.get(student_id='SIGNUP001')
        self.client.force_login(admin)

        response = self.client.post(
            reverse('students:class_placement'),
            {
                'student': student.pk,
                'current_class': target_class.pk,
            },
        )

        self.assertRedirects(response, reverse('students:class_placement'))
        student.refresh_from_db()
        self.assertEqual(student.current_class, target_class)

    def test_admin_can_assign_teacher_subject_class_from_frontend(self):
        admin = User.objects.create_user(
            email='assignment.admin@example.com',
            password='SecurePass123!',
            first_name='Assignment',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=admin,
            role=InstitutionMembership.MembershipRole.OWNER,
        )
        teacher_user = User.objects.create_user(
            email='assignment.teacher@example.com',
            password='SecurePass123!',
            first_name='Assignment',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        teacher = Teacher.objects.create(
            user=teacher_user,
            employee_id='SIGNUP-T002',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date='2026-01-01',
            qualification='BEd',
            phone_number='260970000007',
            address='Lusaka',
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=teacher_user,
            role=InstitutionMembership.MembershipRole.TEACHER,
        )
        subject = Subject.objects.create(name='Assignment Science', code='ASSIGN-SCI')
        room = Room.objects.create(name='Assignment Room 1', capacity=40)
        time_slot = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.MONDAY,
            start_time='08:00',
            end_time='09:00',
            period_number=1,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('teachers:class_subject_assignment'),
            {
                'teacher': teacher.pk,
                'subject': subject.pk,
                'class_obj': self.class_obj.pk,
                'room': room.pk,
                'time_slot': time_slot.pk,
                'is_primary_subject': 'on',
            },
        )

        self.assertRedirects(response, reverse('teachers:class_subject_assignment'))
        self.assertTrue(TeacherSubject.objects.filter(teacher=teacher, subject=subject, is_primary=True).exists())
        self.assertTrue(
            ClassSchedule.objects.filter(
                teacher=teacher,
                subject=subject,
                class_obj=self.class_obj,
                room=room,
                time_slot=time_slot,
                is_active=True,
            ).exists()
        )
