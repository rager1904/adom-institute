from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from students.models import AcademicYear, Class, Student
from teachers.models import Subject, Teacher
from .models import ClassSchedule, Room, TimeSlot


class TimetableFrontendTests(TestCase):
    def setUp(self):
        self.teacher_user = User.objects.create_user(
            email='teacher.schedule@example.com',
            password='pass12345',
            first_name='Teacher',
            last_name='Schedule',
            user_type=User.UserType.TEACHER,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='TT001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            employment_status=Teacher.EmploymentStatus.ACTIVE,
            joining_date=date(2025, 1, 1),
            qualification='BEd',
            specialization='Mathematics',
            phone_number='260970000001',
            address='Lusaka',
        )
        self.student_user = User.objects.create_user(
            email='student.schedule@example.com',
            password='pass12345',
            first_name='Student',
            last_name='Schedule',
            user_type=User.UserType.STUDENT,
        )
        self.other_student_user = User.objects.create_user(
            email='other.schedule@example.com',
            password='pass12345',
            first_name='Other',
            last_name='Schedule',
            user_type=User.UserType.STUDENT,
        )
        self.academic_year = AcademicYear.objects.create(
            name='Schedule Year',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        self.student_class = Class.objects.create(
            name='8A-Schedule',
            display_name='Grade 8A',
            academic_year=self.academic_year,
            capacity=40,
        )
        self.other_class = Class.objects.create(
            name='9B-Schedule',
            display_name='Grade 9B',
            academic_year=self.academic_year,
            capacity=40,
        )
        Student.objects.create(
            user=self.student_user,
            student_id='SCH001',
            admission_number='ADM-SCH001',
            gender=Student.Gender.MALE,
            date_of_birth=date(2012, 1, 1),
            address='Lusaka',
            current_class=self.student_class,
            admission_date=date(2024, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        Student.objects.create(
            user=self.other_student_user,
            student_id='SCH002',
            admission_number='ADM-SCH002',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2012, 1, 1),
            address='Lusaka',
            current_class=self.other_class,
            admission_date=date(2024, 1, 1),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.subject = Subject.objects.create(name='Mathematics Schedule', code='MATH-SCH')
        self.room = Room.objects.create(name='Room Schedule 1', capacity=40)
        self.time_slot = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.MONDAY,
            start_time=time(8, 0),
            end_time=time(9, 0),
            period_number=1,
        )
        self.visible_schedule = ClassSchedule.objects.create(
            class_obj=self.student_class,
            subject=self.subject,
            teacher=self.teacher,
            room=self.room,
            time_slot=self.time_slot,
        )
        self.hidden_time_slot = TimeSlot.objects.create(
            day=TimeSlot.DayOfWeek.TUESDAY,
            start_time=time(8, 0),
            end_time=time(9, 0),
            period_number=1,
        )
        self.hidden_schedule = ClassSchedule.objects.create(
            class_obj=self.other_class,
            subject=self.subject,
            teacher=self.teacher,
            room=self.room,
            time_slot=self.hidden_time_slot,
        )

    def test_my_schedule_is_scoped_to_student_class(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('timetable:my_schedule'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mathematics Schedule')
        self.assertContains(response, 'Grade 8A')
        self.assertNotContains(response, 'Grade 9B')

    def test_student_cannot_open_other_class_schedule_detail(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('timetable:schedule_detail', args=[self.hidden_schedule.pk]))

        self.assertEqual(response.status_code, 404)
