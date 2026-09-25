from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Message, MessageRecipient


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
