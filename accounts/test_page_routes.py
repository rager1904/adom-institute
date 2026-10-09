from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from academics.models import Assignment, Exam, ExamType, StudentAssignment
from accounts.models import Institution, User
from analytics.models import Report
from attendance.models import Attendance, LeaveRequest
from communication.models import CommunicationLog, EmailTemplate, Notification, SMSTemplate
from adom_institute.models import AIUsageLedger, AgentTask
from library.models import Book, BookCategory, DigitalResource
from students.models import AcademicYear, Class, Parent, Student
from teachers.models import Subject, Teacher


class ADOMInstitutePageRouteTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(name='Route School', code='ROUTE')
        self.year = AcademicYear.objects.create(
            institution=self.institution,
            name='Route 2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.class_obj = Class.objects.create(
            name='ROUTE-G10',
            display_name='Route Grade 10',
            academic_year=self.year,
            capacity=40,
        )
        self.user = User.objects.create_user(
            email='route-admin@example.com',
            password='password123',
            first_name='Route',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
            is_staff=True,
            is_superuser=True,
        )
        self.student_user = User.objects.create_user(
            email='route-student@example.com',
            password='password123',
            first_name='Route',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='ROUTE001',
            admission_number='ADM-ROUTE001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2010, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2026, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.teacher_user = User.objects.create_user(
            email='route-teacher@example.com',
            password='password123',
            first_name='Route',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='ROUTE-T001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date(2026, 1, 1),
            qualification='BEd',
            phone_number='260970000000',
            address='Lusaka',
        )
        self.subject = Subject.objects.create(name='Route Mathematics', code='R-MATH')

    def test_public_home_page_exists(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ADOM Institute')
        self.assertContains(response, 'Empowering Education')
        self.assertContains(response, 'Explore Our Courses')
        self.assertContains(response, 'Shop Educational Products')

    def test_ai_hub_page_exists_for_authenticated_users(self):
        AgentTask.objects.create(
            institution=self.institution,
            created_by=self.user,
            agent_key='zambian_curriculum',
            input_payload={'subject': 'Mathematics'},
        )
        AIUsageLedger.objects.create(
            institution=self.institution,
            user=self.user,
            provider='ollama',
            model_name='qwen2.5:7b-instruct',
            prompt_tokens=10,
            total_tokens=10,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('accounts:ai_hub'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open-Source AI Hub')
        self.assertContains(response, 'Zambian Curriculum Agent')
        self.assertContains(response, 'Knowledge Documents')
        self.assertContains(response, 'Usage Entries')
        self.assertContains(response, 'Recent Agent Tasks')

    def test_api_v1_mounts_direct_routers_not_web_urlconfs(self):
        self.client.force_login(self.user)

        api_response = self.client.get('/api/v1/students/students/')
        web_response = self.client.get('/api/v1/students/students/create/')

        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(web_response.status_code, 404)

    def test_student_list_page_renders_age_without_now_context(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('students:student_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'years')

    def test_academics_dashboard_page_exists(self):
        exam_type = ExamType.objects.create(name='Route Midterm')
        Exam.objects.create(
            name='Route Algebra Exam',
            exam_type=exam_type,
            academic_year=self.year,
            class_obj=self.class_obj,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 1),
            total_marks=100,
            passing_marks=50,
        )
        Assignment.objects.create(
            title='Route Homework',
            description='Dynamic route assignment',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
            max_marks=10,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('academics:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Academic Management')
        self.assertContains(response, 'Route Algebra Exam')
        self.assertContains(response, 'Route Homework')

    def test_object_pages_render_for_seeded_records(self):
        parent_user = User.objects.create_user(
            email='route-parent@example.com',
            password='password123',
            first_name='Route',
            last_name='Parent',
            user_type=User.UserType.PARENT,
        )
        parent = Parent.objects.create(
            student=self.student,
            user=parent_user,
            relationship=Parent.Relationship.GUARDIAN,
            phone_number='260960000000',
            email='route-parent@example.com',
        )
        assignment = Assignment.objects.create(
            title='Route Submission Task',
            description='Dynamic submission task',
            subject=self.subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date=datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
            max_marks=10,
        )
        submission = StudentAssignment.objects.create(
            student=self.student,
            assignment=assignment,
            submission_file='assignment_submissions/route.pdf',
            submission_text='Complete',
            marks_obtained=Decimal('8.00'),
        )
        attendance = Attendance.objects.create(
            student=self.student,
            date=date(2026, 6, 1),
            status=Attendance.AttendanceStatus.PRESENT,
            marked_by=self.teacher,
        )
        leave_request = LeaveRequest.objects.create(
            student=self.student,
            leave_type=LeaveRequest.LeaveType.SICK_LEAVE,
            start_date=date(2026, 6, 3),
            end_date=date(2026, 6, 4),
            reason='Medical appointment',
        )
        category = BookCategory.objects.create(name='Route Library')
        book = Book.objects.create(
            title='Route Book',
            author='Route Author',
            category=category,
            isbn='9780000000012',
        )
        resource = DigitalResource.objects.create(
            title='Route Resource',
            resource_type='pdf',
            file='library/digital/route.pdf',
            uploaded_by=self.user,
        )

        self.client.force_login(self.user)
        checks = [
            reverse('students:student_detail', args=[self.student.pk]),
            reverse('students:class_detail', args=[self.class_obj.pk]),
            reverse('students:class_delete', args=[self.class_obj.pk]),
            reverse('students:parent_detail', args=[parent.pk]),
            reverse('academics:student_assignment_detail', args=[submission.pk]),
            reverse('attendance:attendance_detail', args=[attendance.pk]),
            reverse('attendance:attendance_update', args=[attendance.pk]),
            reverse('attendance:leave_request_detail', args=[leave_request.pk]),
            reverse('attendance:leave_approval', args=[leave_request.pk]),
            reverse('teachers:teacher_update', args=[self.teacher.pk]),
            reverse('library:book_detail', args=[book.pk]),
            reverse('library:digital_resource_detail', args=[resource.pk]),
        ]

        for url in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertLess(response.status_code, 400)

    def test_communication_and_analytics_linked_pages_render(self):
        report = Report.objects.create(
            name='Route Analytics Report',
            report_type=Report.ReportType.CUSTOM,
            description='Regression report',
            report_format=Report.ReportFormat.PDF,
            generated_by=self.user,
        )
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=Notification.NotificationType.SYSTEM,
            title='Route Notification',
            message='Regression notification',
        )
        email_template = EmailTemplate.objects.create(
            name='Route Email Template',
            template_type=EmailTemplate.TemplateType.CUSTOM,
            subject='Route subject',
            content='Hello {{ name }}',
            variables={'name': 'Student'},
        )
        sms_template = SMSTemplate.objects.create(
            name='Route SMS Template',
            template_type=SMSTemplate.TemplateType.CUSTOM,
            content='Hello {{ name }}',
            variables={'name': 'Student'},
        )
        log = CommunicationLog.objects.create(
            recipient=self.user,
            communication_type=CommunicationLog.CommunicationType.IN_APP,
            status=CommunicationLog.CommunicationStatus.SENT,
            subject='Route log',
            content='Regression communication log',
            related_notification=notification,
        )

        self.client.force_login(self.user)
        checks = [
            reverse('analytics:report_create'),
            reverse('analytics:report_detail', args=[report.pk]),
            reverse('analytics:report_update', args=[report.pk]),
            reverse('analytics:report_delete', args=[report.pk]),
            reverse('communication:communication_report'),
            reverse('communication:communication_log_list'),
            reverse('communication:communication_log_detail', args=[log.pk]),
            reverse('communication:notification_detail', args=[notification.pk]),
            reverse('communication:notification_update', args=[notification.pk]),
            reverse('communication:email_template_list'),
            reverse('communication:email_template_create'),
            reverse('communication:email_template_detail', args=[email_template.pk]),
            reverse('communication:email_template_update', args=[email_template.pk]),
            reverse('communication:sms_template_list'),
            reverse('communication:sms_template_create'),
            reverse('communication:sms_template_detail', args=[sms_template.pk]),
            reverse('communication:sms_template_update', args=[sms_template.pk]),
        ]

        for url in checks:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertLess(response.status_code, 400)
