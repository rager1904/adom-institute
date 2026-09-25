from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Institution, InstitutionMembership, User
from students.models import AcademicYear, Class, Student
from teachers.models import Subject, Teacher
from timetable.models import ClassSchedule, Room, TimeSlot
from .models import Attendance
from .views import AttendanceViewSet


class AttendanceRegressionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.teacher_user = User.objects.create_user(
            email='attendance-teacher@example.com',
            password='password123',
            first_name='Attendance',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='AT001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date.today(),
            qualification='BEd',
            phone_number='260970000002',
            address='Lusaka',
        )
        self.institution = Institution.objects.create(name='Attendance School', code='ATT-SCHOOL')
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
            name='G9A',
            display_name='Grade 9 A',
            academic_year=self.year,
            capacity=40,
        )
        self.subject = Subject.objects.create(name='Mathematics', code='MATH')
        self.room = Room.objects.create(name='Room A', capacity=40)
        self.time_slot = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.MONDAY,
            start_time='08:00',
            end_time='09:00',
            period_number=1,
        )
        ClassSchedule.objects.create(
            class_obj=self.class_obj,
            subject=self.subject,
            teacher=self.teacher,
            room=self.room,
            time_slot=self.time_slot,
        )
        student_user = User.objects.create_user(
            email='attendance-student@example.com',
            password='password123',
            first_name='Attendance',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        self.student = Student.objects.create(
            user=student_user,
            student_id='AS001',
            admission_number='ADM-AS001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2011, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

    def test_bulk_attendance_uses_teacher_profile_related_name(self):
        request = self.factory.post(
            '/api/v1/attendance/api/attendance/bulk_create/',
            {
                'class_obj': self.class_obj.pk,
                'date': '2026-06-13',
                'attendances': [
                    {'student_id': self.student.pk, 'status': Attendance.AttendanceStatus.PRESENT}
                ],
            },
            format='json',
        )
        force_authenticate(request, user=self.teacher_user)
        response = AttendanceViewSet.as_view({'post': 'bulk_create'})(request)

        self.assertEqual(response.status_code, 200)
        attendance = Attendance.objects.get(student=self.student, date='2026-06-13')
        self.assertEqual(attendance.marked_by, self.teacher)

    def test_bulk_attendance_rejects_user_without_teacher_profile(self):
        user = User.objects.create_user(
            email='not-a-teacher@example.com',
            password='password123',
            first_name='Plain',
            last_name='User',
            user_type=User.UserType.STUDENT,
        )
        request = self.factory.post(
            '/api/v1/attendance/api/attendance/bulk_create/',
            {
                'class_obj': self.class_obj.pk,
                'date': '2026-06-13',
                'attendances': [
                    {'student_id': self.student.pk, 'status': Attendance.AttendanceStatus.PRESENT}
                ],
            },
            format='json',
        )
        force_authenticate(request, user=user)
        response = AttendanceViewSet.as_view({'post': 'bulk_create'})(request)

        self.assertEqual(response.status_code, 403)

    def test_bulk_attendance_rejects_student_outside_teacher_institution(self):
        other_institution = Institution.objects.create(name='Other School', code='OTHER-SCHOOL')
        other_year = AcademicYear.objects.create(
            institution=other_institution,
            name='2027',
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
        )
        other_class = Class.objects.create(
            name='OTHER-G9',
            display_name='Other Grade 9',
            academic_year=other_year,
            capacity=40,
        )
        other_user = User.objects.create_user(
            email='other-student@example.com',
            password='password123',
            first_name='Other',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        other_student = Student.objects.create(
            user=other_user,
            student_id='OS001',
            admission_number='ADM-OS001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2011, 1, 1),
            address='Lusaka',
            current_class=other_class,
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )

        request = self.factory.post(
            '/api/v1/attendance/api/attendance/bulk_create/',
            {
                'class_obj': other_class.pk,
                'date': '2026-06-13',
                'attendances': [
                    {'student_id': other_student.pk, 'status': Attendance.AttendanceStatus.PRESENT}
                ],
            },
            format='json',
        )
        force_authenticate(request, user=self.teacher_user)
        response = AttendanceViewSet.as_view({'post': 'bulk_create'})(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Attendance.objects.filter(student=other_student).exists())

    def test_my_attendance_page_renders_student_records(self):
        Attendance.objects.create(
            student=self.student,
            date=date(2026, 6, 16),
            status=Attendance.AttendanceStatus.PRESENT,
            marked_by=self.teacher,
        )
        self.client.force_login(self.student.user)

        response = self.client.get(reverse('attendance:my_attendance'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Attendance')
        self.assertContains(response, 'Attendance Student')
        self.assertContains(response, 'Present')
