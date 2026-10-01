"""Assignment material and submissions are read-only for everyone but staff."""

from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.urls import reverse
from django.utils import timezone

from accounts.models import Institution, InstitutionMembership, User
from students.models import AcademicYear, Class, Student
from teachers.models import Subject, Teacher
from .models import Assignment, StudentAssignment

BRIEF_BYTES = b'%PDF-1.4 assignment brief'
HOMEWORK_BYTES = b'%PDF-1.4 student homework'


class AssignmentMaterialReadOnlyTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            email='assignment-teacher@example.com',
            password='password123',
            first_name='Assign',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T-RO-001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date.today(),
            qualification='BEd',
            phone_number='260970000101',
            address='Lusaka',
        )
        self.institution = Institution.objects.create(name='Read Only School', code='RO-SCHOOL')
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=self.teacher_user,
            role=InstitutionMembership.MembershipRole.TEACHER,
        )
        self.year = AcademicYear.objects.create(
            institution=self.institution,
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            name='G12R',
            display_name='Grade 12 R',
            academic_year=self.year,
            capacity=40,
        )
        self.subject = Subject.objects.create(name='Biology', code='BIO')
        self.assignment = Assignment.objects.create(
            title='Cell Structure Brief',
            description='Read the brief and answer the questions.',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=50,
            attachment=SimpleUploadedFile('brief.pdf', BRIEF_BYTES),
        )
        self.student = self.create_student('ro-student@example.com', 'S-RO1')
        self.other_student = self.create_student('ro-other-student@example.com', 'S-RO2')
        self.submission = StudentAssignment.objects.create(
            student=self.student,
            assignment=self.assignment,
            submission_file=SimpleUploadedFile('homework.pdf', HOMEWORK_BYTES),
        )

    def create_student(self, email, student_id):
        user = User.objects.create_user(
            email=email,
            password='password123',
            first_name='Read',
            last_name=student_id,
            user_type=User.UserType.STUDENT,
        )
        student = Student.objects.create(
            user=user,
            student_id=student_id,
            admission_number=f'ADM-{student_id}',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2008, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.class_obj.students.add(student)
        return student

    def assert_inline(self, response, expected_bytes):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('inline;'))
        self.assertNotIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(b''.join(response.streaming_content), expected_bytes)

    def test_assignment_attachment_requires_sign_in(self):
        response = self.client.get(
            reverse('academics:assignment_file', args=[self.assignment.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_student_reads_assignment_attachment_inline(self):
        self.client.force_login(self.student.user)

        response = self.client.get(
            reverse('academics:assignment_file', args=[self.assignment.pk])
        )

        self.assert_inline(response, BRIEF_BYTES)

    def test_outsider_cannot_read_assignment_attachment(self):
        Class.objects.create(
            name='G99X',
            display_name='Grade 99 X',
            academic_year=self.year,
            capacity=10,
        )
        outsider_user = User.objects.create_user(
            email='ro-outsider@example.com',
            password='password123',
            first_name='Out',
            last_name='Sider',
            user_type=User.UserType.STUDENT,
        )
        outsider = Student.objects.create(
            user=outsider_user,
            student_id='S-RO9',
            admission_number='ADM-S-RO9',
            gender=Student.Gender.MALE,
            date_of_birth=date(2008, 1, 1),
            address='Lusaka',
            current_class=Class.objects.get(name='G99X'),
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.client.force_login(outsider.user)

        response = self.client.get(
            reverse('academics:assignment_file', args=[self.assignment.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_raw_media_url_for_assignment_attachment_returns_404(self):
        self.client.force_login(self.student.user)

        response = self.client.get(f'/media/{self.assignment.attachment.name}')

        self.assertEqual(response.status_code, 404)

    def test_raw_media_url_for_submission_returns_404(self):
        self.client.force_login(self.student.user)

        response = self.client.get(f'/media/{self.submission.submission_file.name}')

        self.assertEqual(response.status_code, 404)

    def test_student_reads_own_submission_inline(self):
        self.client.force_login(self.student.user)

        response = self.client.get(
            reverse('academics:submission_file', args=[self.submission.pk])
        )

        self.assert_inline(response, HOMEWORK_BYTES)

    def test_student_cannot_read_another_students_submission(self):
        self.client.force_login(self.other_student.user)

        response = self.client.get(
            reverse('academics:submission_file', args=[self.submission.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_teacher_reads_student_submission_inline(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(
            reverse('academics:submission_file', args=[self.submission.pk])
        )

        self.assert_inline(response, HOMEWORK_BYTES)

    def test_api_never_exposes_raw_attachment_urls(self):
        self.client.force_login(self.student.user)

        response = self.client.get(
            reverse('academics_api:assignment-detail', args=[self.assignment.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn('attachment', payload)
        self.assertEqual(
            payload['attachment_url'],
            reverse('academics:assignment_file', args=[self.assignment.pk]),
        )
        self.assertNotIn('/media/', response.content.decode())

    def test_api_never_exposes_raw_submission_urls(self):
        self.client.force_login(self.student.user)

        response = self.client.get(
            reverse('academics_api:studentassignment-detail', args=[self.submission.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn('submission_file', payload)
        self.assertEqual(
            payload['submission_file_url'],
            reverse('academics:submission_file', args=[self.submission.pk]),
        )
        self.assertNotIn('/media/', response.content.decode())

    def test_student_cannot_edit_another_students_submission_via_api(self):
        self.client.force_login(self.other_student.user)

        response = self.client.patch(
            reverse('academics_api:studentassignment-detail', args=[self.submission.pk]),
            data={'submission_text': 'tampered'},
        )

        # 404 rather than 403: the other student's submission is not even
        # visible to this user, so its existence is not disclosed.
        self.assertEqual(response.status_code, 404)
        self.submission.refresh_from_db()
        self.assertNotEqual(self.submission.submission_text, 'tampered')

    def test_student_can_edit_own_submission_via_api(self):
        self.client.force_login(self.student.user)

        # The viewset only accepts multipart/form-data because submissions
        # carry an uploaded file.
        response = self.client.patch(
            reverse('academics_api:studentassignment-detail', args=[self.submission.pk]),
            data=encode_multipart(BOUNDARY, {'submission_text': 'revised answer'}),
            content_type=MULTIPART_CONTENT,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.submission_text, 'revised answer')

    def test_student_cannot_open_another_students_submission_update_form(self):
        self.client.force_login(self.other_student.user)

        response = self.client.get(
            reverse('academics:student_assignment_update', args=[self.submission.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_assignment_page_links_to_protected_attachment_not_raw_media(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(
            reverse('academics:assignment_detail', args=[self.assignment.pk])
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(
            reverse('academics:assignment_file', args=[self.assignment.pk]),
            body,
        )
        self.assertNotIn(f'/media/{self.assignment.attachment.name}', body)

    def test_submission_page_links_to_protected_file_not_raw_media(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(
            reverse('academics:student_assignment_detail', args=[self.submission.pk])
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(
            reverse('academics:submission_file', args=[self.submission.pk]),
            body,
        )
        self.assertNotIn(f'/media/{self.submission.submission_file.name}', body)

    def test_submission_update_form_exposes_no_raw_media_url(self):
        self.client.force_login(self.student.user)

        response = self.client.get(
            reverse('academics:student_assignment_update', args=[self.submission.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f'/media/{self.submission.submission_file.name}', response.content.decode())
