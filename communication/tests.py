from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Institution, InstitutionMembership, User
from students.models import AcademicYear, Class, Student
from teachers.models import Teacher
from .models import Announcement, Message, MessageRecipient
from .forms import MessageForm


class CommunicationFrontendTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            email='teacher@example.com',
            password='pass12345',
            first_name='Teach',
            last_name='Sender',
            user_type=User.UserType.TEACHER,
        )
        self.recipient = User.objects.create_user(
            email='student@example.com',
            password='pass12345',
            first_name='Student',
            last_name='Receiver',
            user_type=User.UserType.STUDENT,
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='pass12345',
            first_name='Other',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )

    def test_inbox_shows_only_current_user_received_messages(self):
        visible_message = Message.objects.create(
            sender=self.sender,
            subject='Your assignment feedback',
            content='Please review the notes before class.',
            is_important=True,
        )
        visible_message.recipients.add(self.recipient)
        MessageRecipient.objects.create(
            message=visible_message,
            recipient=self.recipient,
            is_read=False,
        )

        hidden_message = Message.objects.create(
            sender=self.sender,
            subject='Private message for another student',
            content='This should not be visible.',
        )
        hidden_message.recipients.add(self.other_user)
        MessageRecipient.objects.create(
            message=hidden_message,
            recipient=self.other_user,
            is_read=False,
        )

        self.client.force_login(self.recipient)
        response = self.client.get(reverse('communication:inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your assignment feedback')
        self.assertContains(response, 'Unread')
        self.assertContains(response, 'Important')
        self.assertNotContains(response, 'Private message for another student')


class CommunicationRecipientScopeTests(TestCase):
    """Regression coverage for the message composer recipient list.

    The role branches tested ``hasattr(user, 'teacher')``/``hasattr(user,
    'student')`` but the related names are ``teacher_profile``/
    ``student_profile``, so students fell through to the unrestricted
    ``User.objects.all()`` queryset and could address anybody.
    """

    def setUp(self):
        self.institution = Institution.objects.create(name='Comms School', code='COMMS')
        self.other_institution = Institution.objects.create(name='Comms Other', code='COMMS-OTHER')
        self.student_user = User.objects.create_user(
            email='comms-student@example.com',
            password='pass12345',
            first_name='Comms',
            last_name='Student',
            user_type=User.UserType.STUDENT,
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=self.student_user,
            role=InstitutionMembership.MembershipRole.STUDENT,
        )
        Student.objects.create(
            user=self.student_user,
            student_id='COMMS-S001',
            admission_number='ADM-COMMS-S001',
            gender=Student.Gender.FEMALE,
            date_of_birth=date(2011, 1, 1),
            address='Lusaka',
            admission_date=date.today(),
            admission_status=Student.AdmissionStatus.APPROVED,
        )
        self.teacher_user = User.objects.create_user(
            email='comms-teacher@example.com',
            password='pass12345',
            first_name='Comms',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=self.teacher_user,
            role=InstitutionMembership.MembershipRole.TEACHER,
        )
        Teacher.objects.create(
            user=self.teacher_user,
            employee_id='COMMS-T001',
            employment_type=Teacher.EmploymentType.FULL_TIME,
            joining_date=date.today(),
            qualification='BEd',
            phone_number='260970000013',
            address='Lusaka',
        )
        self.other_student_user = User.objects.create_user(
            email='comms-other-student@example.com',
            password='pass12345',
            first_name='Comms',
            last_name='Other',
            user_type=User.UserType.STUDENT,
        )
        InstitutionMembership.objects.create(
            institution=self.other_institution,
            user=self.other_student_user,
            role=InstitutionMembership.MembershipRole.STUDENT,
        )

    def test_student_cannot_address_other_students(self):
        form = MessageForm(user=self.student_user)

        recipients = set(form.fields['recipients'].queryset.values_list('pk', flat=True))

        self.assertNotIn(self.other_student_user.pk, recipients)
        self.assertNotIn(self.student_user.pk, recipients)
        self.assertIn(self.teacher_user.pk, recipients)

    def test_student_cannot_address_users_of_another_institution(self):
        form = MessageForm(user=self.student_user)

        recipients = set(form.fields['recipients'].queryset.values_list('pk', flat=True))

        self.assertNotIn(self.other_student_user.pk, recipients)

    def test_student_cannot_send_a_message_to_an_unreachable_recipient(self):
        form = MessageForm(
            {
                'recipients': [self.other_student_user.pk],
                'subject': 'Cross tenant',
                'content': 'Should not be accepted.',
                'message_type': Message.MessageType.DIRECT,
            },
            user=self.student_user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('recipients', form.errors)

    def test_message_composer_omits_unreachable_recipients(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('communication:message_create'))

        self.assertEqual(response.status_code, 200)
        offered = set(
            response.context['form'].fields['recipients'].queryset.values_list('pk', flat=True)
        )
        self.assertNotIn(self.other_student_user.pk, offered)

    def test_get_users_for_message_omits_other_institution(self):
        self.client.force_login(self.student_user)

        response = self.client.get('/communication/ajax/users-for-message/')

        self.assertEqual(response.status_code, 200)
        returned = {item['id'] for item in response.json()['users']}
        self.assertNotIn(self.other_student_user.pk, returned)
        self.assertIn(self.teacher_user.pk, returned)

    def test_announcement_form_only_offers_own_institution_classes(self):
        year = AcademicYear.objects.create(
            institution=self.institution,
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
        )
        own_class = Class.objects.create(
            name='COMMS-A',
            display_name='Comms A',
            academic_year=year,
            capacity=40,
        )
        other_year = AcademicYear.objects.create(
            institution=self.other_institution,
            name='2027',
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            is_active=True,
        )
        other_class = Class.objects.create(
            name='COMMS-B',
            display_name='Comms B',
            academic_year=other_year,
            capacity=40,
        )
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('communication:announcement_create'))

        self.assertEqual(response.status_code, 200)
        offered = set(
            response.context['form'].fields['target_classes'].queryset.values_list('pk', flat=True)
        )
        self.assertNotIn(other_class.pk, offered)
        self.assertIn(own_class.pk, offered)

    def test_announcement_list_hides_other_institution_announcements(self):
        own_announcement = Announcement.objects.create(
            title='Own institution notice',
            content='Only for our school.',
            announcement_type=Announcement.AnnouncementType.GENERAL,
            target_audience=Announcement.TargetAudience.ALL,
            is_published=True,
            published_by=self.teacher_user,
        )
        other_announcement = Announcement.objects.create(
            title='Other institution notice',
            content='Should stay hidden.',
            announcement_type=Announcement.AnnouncementType.GENERAL,
            target_audience=Announcement.TargetAudience.ALL,
            is_published=True,
            published_by=self.other_student_user,
        )
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('communication:announcement_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Own institution notice')
        self.assertNotContains(response, 'Other institution notice')

    def test_announcement_detail_hides_other_institution_announcement(self):
        other_announcement = Announcement.objects.create(
            title='Other institution detail',
            content='Should stay hidden.',
            announcement_type=Announcement.AnnouncementType.GENERAL,
            target_audience=Announcement.TargetAudience.ALL,
            is_published=True,
            published_by=self.other_student_user,
        )
        self.client.force_login(self.student_user)

        response = self.client.get(
            reverse('communication:announcement_detail', kwargs={'pk': other_announcement.pk})
        )

        self.assertEqual(response.status_code, 404)
