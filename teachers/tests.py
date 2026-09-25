from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from academics.models import Assignment
from students.models import AcademicYear, Class, Student
from timetable.models import ClassSchedule, Room, TimeSlot
from .models import Subject, Teacher


class TeacherFrontendTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            email='my-teaching@example.com',
            password='pass12345',
            first_name='My',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='MYT001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            employment_status=Teacher.EmploymentStatus.ACTIVE,
            joining_date=date(2025, 1, 1),
            qualification='BEd',
            phone_number='260970000001',
            address='Lusaka',
        )
        other_user = User.objects.create_user(
            email='other-teaching@example.com',
            password='pass12345',
            first_name='Other',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.other_teacher = Teacher.objects.create(
            user=other_user,
            employee_id='MYT002',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            employment_status=Teacher.EmploymentStatus.ACTIVE,
            joining_date=date(2025, 1, 1),
            qualification='BEd',
            phone_number='260970000002',
            address='Lusaka',
        )
        year = AcademicYear.objects.create(
            name='Teacher Frontend Year',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.class_obj = Class.objects.create(
            name='MYT-8A',
            display_name='My Teaching Grade 8A',
            academic_year=year,
            capacity=40,
        )
        self.other_class = Class.objects.create(
            name='MYT-9B',
            display_name='Other Teaching Grade 9B',
            academic_year=year,
            capacity=40,
        )
        student_user = User.objects.create_user(
            email='my-teaching-student@example.com',
            password='pass12345',
            first_name='Teaching',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        Student.objects.create(
            user=student_user,
            student_id='MYTS001',
            admission_number='ADM-MYTS001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2012, 1, 1),
            address='Lusaka',
            current_class=self.class_obj,
            admission_date=date(2024, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        subject = Subject.objects.create(name='My Teaching Mathematics', code='MYT-MATH')
        room = Room.objects.create(name='My Teaching Room', capacity=40)
        monday = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.MONDAY,
            start_time=time(8, 0),
            end_time=time(9, 0),
            period_number=1,
        )
        tuesday = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.TUESDAY,
            start_time=time(8, 0),
            end_time=time(9, 0),
            period_number=1,
        )
        ClassSchedule.objects.create(
            class_obj=self.class_obj,
            subject=subject,
            teacher=self.teacher,
            room=room,
            time_slot=monday,
        )
        ClassSchedule.objects.create(
            class_obj=self.other_class,
            subject=subject,
            teacher=self.other_teacher,
            room=room,
            time_slot=tuesday,
        )
        Assignment.objects.create(
            title='My Teaching Assignment',
            description='Visible assignment',
            subject=subject,
            class_obj=self.class_obj,
            teacher=self.teacher,
            due_date='2026-07-01T12:00:00Z',
            max_marks=100,
        )
        Assignment.objects.create(
            title='Other Teaching Assignment',
            description='Hidden assignment',
            subject=subject,
            class_obj=self.other_class,
            teacher=self.other_teacher,
            due_date='2026-07-01T12:00:00Z',
            max_marks=100,
        )

    def test_my_teaching_page_is_scoped_to_logged_in_teacher(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('teachers:my_teaching'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Teaching')
        self.assertContains(response, 'My Teaching Grade 8A')
        self.assertContains(response, 'My Teaching Assignment')
        self.assertNotContains(response, 'Other Teaching Grade 9B')
        self.assertNotContains(response, 'Other Teaching Assignment')
