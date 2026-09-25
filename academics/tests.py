from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Institution, InstitutionMembership, User
from attendance.models import Attendance
from library.models import DigitalResource
from students.models import AcademicYear, Class, Student
from teachers.models import Subject, Teacher
from .models import Assignment, ExamType, Exam, ExamSubject, Grade, StudentAssignment, StudentExamResult
from .views import ExamViewSet, StudentExamResultViewSet


class AcademicWorkflowRegressionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.teacher_user = User.objects.create_user(
            email='teacher@example.com',
            password='password123',
            first_name='Test',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date.today(),
            qualification='BEd',
            phone_number='260970000001',
            address='Lusaka',
        )
        self.institution = Institution.objects.create(
            name='Test School',
            code='TEST-SCHOOL',
        )
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
            name='G12A',
            display_name='Grade 12 A',
            academic_year=self.year,
            capacity=40,
        )
        self.subject = Subject.objects.create(name='Mathematics', code='MATH')
        self.exam_type = ExamType.objects.create(name='Midterm', weightage=Decimal('40.00'))
        self.exam = Exam.objects.create(
            name='Midterm 1',
            exam_type=self.exam_type,
            academic_year=self.year,
            class_obj=self.class_obj,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            total_marks=100,
            passing_marks=50,
        )
        self.exam_subject = ExamSubject.objects.create(
            exam=self.exam,
            subject=self.subject,
            max_marks=100,
            passing_marks=50,
            exam_date=date.today(),
            duration=120,
        )
        self.grade_a = Grade.objects.create(name='A', min_marks=75, max_marks=100, grade_point=Decimal('4.00'))
        self.grade_f = Grade.objects.create(name='F', min_marks=0, max_marks=49, grade_point=Decimal('0.00'))

    def create_student(self, email, student_id):
        user = User.objects.create_user(
            email=email,
            password='password123',
            first_name='Test',
            last_name=student_id,
            user_type=User.UserType.STUDENT,
        )
        return Student.objects.create(
            user=user,
            student_id=student_id,
            admission_number=f'ADM-{student_id}',
            gender=Student.Gender.MALE,
            date_of_birth=date(2008, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def test_exam_results_summary_uses_database_annotations(self):
        student_one = self.create_student('student1@example.com', 'S001')
        student_two = self.create_student('student2@example.com', 'S002')
        StudentExamResult.objects.create(
            student=student_one,
            exam_subject=self.exam_subject,
            marks_obtained=Decimal('80.00'),
            grade=self.grade_a,
            created_by=self.teacher,
        )
        StudentExamResult.objects.create(
            student=student_two,
            exam_subject=self.exam_subject,
            marks_obtained=Decimal('40.00'),
            grade=self.grade_f,
            created_by=self.teacher,
        )

        request = self.factory.get('/api/v1/academics/api/exams/1/results_summary/')
        force_authenticate(request, user=self.teacher_user)
        response = ExamViewSet.as_view({'get': 'results_summary'})(request, pk=self.exam.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['passed_students'], 1)
        self.assertEqual(response.data['failed_students'], 1)
        self.assertEqual(float(response.data['average_percentage']), 60.0)
        self.assertEqual(response.data['grade_distribution'], {'A': 1, 'F': 1})

    def test_bulk_grade_entry_sets_teacher_profile(self):
        student = self.create_student('student3@example.com', 'S003')
        request = self.factory.post(
            '/api/v1/academics/api/student-exam-results/bulk_grade_entry/',
            {
                'exam_subject_id': self.exam_subject.pk,
                'grades': [{'student_id': student.pk, 'marks_obtained': '71.00'}],
            },
            format='json',
        )
        force_authenticate(request, user=self.teacher_user)
        response = StudentExamResultViewSet.as_view({'post': 'bulk_grade_entry'})(request)

        self.assertEqual(response.status_code, 200)
        result = StudentExamResult.objects.get(student=student, exam_subject=self.exam_subject)
        self.assertEqual(result.created_by, self.teacher)

    def test_assignment_rejects_executable_attachment(self):
        assignment = Assignment(
            title='Unsafe upload',
            description='Should fail validation',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
            attachment=SimpleUploadedFile('payload.exe', b'MZ'),
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_submission_rejects_oversized_document(self):
        student = self.create_student('large-upload@example.com', 'S004')
        assignment = Assignment.objects.create(
            title='Large upload',
            description='Should fail validation',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
        )
        oversized = SimpleUploadedFile('submission.pdf', b'0' * (20 * 1024 * 1024 + 1))
        submission = StudentAssignment(
            student=student,
            assignment=assignment,
            submission_file=oversized,
        )

        with self.assertRaises(ValidationError):
            submission.full_clean()

    def test_course_frontend_pages_render_existing_academic_data(self):
        Assignment.objects.create(
            title='Course Assignment',
            description='Course workflow',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
        )
        student = self.create_student('course-student@example.com', 'SCOURSE')
        Attendance.objects.create(
            student=student,
            date=date.today(),
            status=Attendance.AttendanceStatus.PRESENT,
            marked_by=self.teacher,
        )
        DigitalResource.objects.create(
            title='Course Resource',
            resource_type='pdf',
            file=SimpleUploadedFile('resource.pdf', b'course resource'),
            subject='Mathematics',
            uploaded_by=self.teacher_user,
        )
        self.client.force_login(self.teacher_user)

        list_response = self.client.get('/academics/courses/')
        detail_response = self.client.get(f'/academics/courses/{self.class_obj.pk}/')

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.class_obj.display_name)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Course Assignment')
        self.assertContains(detail_response, 'Course Resource')
        self.assertContains(detail_response, 'Attendance')
        self.assertContains(detail_response, 'Assignment Progress')

    def test_my_academics_page_renders_student_assignments_and_exams(self):
        student = self.create_student('my-academics@example.com', 'SMYACA')
        Assignment.objects.create(
            title='My Academics Assignment',
            description='Student academic workflow',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
        )
        self.exam_subject.exam_date = date.today() + timedelta(days=7)
        self.exam_subject.save(update_fields=['exam_date'])
        self.client.force_login(student.user)

        response = self.client.get(reverse('academics:my_academics'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Academics')
        self.assertContains(response, 'My Academics Assignment')
        self.assertContains(response, self.exam.name)

    def test_grading_queue_is_scoped_to_teacher_and_saves_grade(self):
        student = self.create_student('grading-queue@example.com', 'SGRADEQ')
        assignment = Assignment.objects.create(
            title='Queue Assignment',
            description='Needs grading',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
        )
        submission = StudentAssignment.objects.create(
            student=student,
            assignment=assignment,
            submission_file=SimpleUploadedFile('submission.pdf', b'%PDF-1.4'),
            submission_text='Submitted work',
        )
        other_teacher_user = User.objects.create_user(
            email='other-grading@example.com',
            password='password123',
            first_name='Other',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        other_teacher = Teacher.objects.create(
            user=other_teacher_user,
            employee_id='T-OTHER-GRADE',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date.today(),
            qualification='BEd',
            phone_number='260970000099',
            address='Lusaka',
        )
        other_assignment = Assignment.objects.create(
            title='Hidden Queue Assignment',
            description='Other teacher work',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=other_teacher,
            due_date=timezone.now() + timedelta(days=7),
            max_marks=100,
        )
        StudentAssignment.objects.create(
            student=student,
            assignment=other_assignment,
            submission_file=SimpleUploadedFile('hidden.pdf', b'%PDF-1.4'),
            submission_text='Hidden work',
        )
        self.client.force_login(self.teacher_user)

        queue_response = self.client.get(reverse('academics:grading_queue'))
        grade_response = self.client.post(
            reverse('academics:grade_submission', args=[submission.pk]),
            {'marks_obtained': '88', 'feedback': 'Strong work'},
        )

        self.assertEqual(queue_response.status_code, 200)
        self.assertContains(queue_response, 'Queue Assignment')
        self.assertNotContains(queue_response, 'Hidden Queue Assignment')
        self.assertEqual(grade_response.status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.marks_obtained, Decimal('88.00'))
        self.assertEqual(submission.feedback, 'Strong work')
