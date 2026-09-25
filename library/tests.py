from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .forms import DigitalResourceUploadForm
from .models import Book, BookCategory, DigitalResource


class LibraryUploadValidationTests(TestCase):
    def test_book_cover_rejects_non_image_extension(self):
        category = BookCategory.objects.create(name='Science')
        book = Book(
            title='Biology',
            author='Teacher',
            category=category,
            cover_image=SimpleUploadedFile('cover.exe', b'MZ'),
        )

        with self.assertRaises(ValidationError):
            book.full_clean()

    def test_digital_resource_rejects_executable_upload(self):
        resource = DigitalResource(
            title='Unsafe resource',
            resource_type='pdf',
            file=SimpleUploadedFile('payload.exe', b'MZ'),
        )

        with self.assertRaises(ValidationError):
            resource.full_clean()

    def test_digital_resource_form_rejects_unsupported_video_extension(self):
        form = DigitalResourceUploadForm(
            data={
                'title': 'Unsupported video',
                'description': 'Should fail upload policy',
                'resource_type': 'video',
                'author': 'Teacher',
                'subject': 'ICT',
                'grade_level': '10',
                'tags': '',
                'access_level': 'students',
                'is_downloadable': 'on',
            },
            files={
                'file': SimpleUploadedFile('lesson.mov', b'video-bytes', content_type='video/quicktime')
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_digital_resource_form_accepts_supported_resource_extension(self):
        form = DigitalResourceUploadForm(
            data={
                'title': 'Supported PDF',
                'description': 'Valid resource',
                'resource_type': 'pdf',
                'author': 'Teacher',
                'subject': 'Science',
                'grade_level': '10',
                'tags': '',
                'access_level': 'students',
                'is_downloadable': 'on',
            },
            files={
                'file': SimpleUploadedFile('lesson.pdf', b'%PDF-1.4', content_type='application/pdf')
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_resource_discovery_filters_by_student_access(self):
        student = User.objects.create_user(
            email='library-student@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )
        DigitalResource.objects.create(
            title='Student Resource',
            resource_type='pdf',
            file=SimpleUploadedFile('student.pdf', b'%PDF-1.4'),
            access_level='students',
        )
        DigitalResource.objects.create(
            title='Teacher Resource',
            resource_type='pdf',
            file=SimpleUploadedFile('teacher.pdf', b'%PDF-1.4'),
            access_level='teachers',
        )
        self.client.force_login(student)

        response = self.client.get('/library/discover/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Resource')
        self.assertNotContains(response, 'Teacher Resource')

    def test_teacher_resource_workspace_is_scoped_to_uploaded_resources(self):
        teacher = User.objects.create_user(
            email='resource-teacher@example.com',
            password='password123',
            first_name='Resource',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        other_teacher = User.objects.create_user(
            email='other-resource-teacher@example.com',
            password='password123',
            first_name='Other',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        DigitalResource.objects.create(
            title='Visible Teacher Notes',
            resource_type='pdf',
            file=SimpleUploadedFile('visible.pdf', b'%PDF-1.4'),
            access_level='students',
            uploaded_by=teacher,
        )
        DigitalResource.objects.create(
            title='Hidden Teacher Notes',
            resource_type='pdf',
            file=SimpleUploadedFile('hidden.pdf', b'%PDF-1.4'),
            access_level='students',
            uploaded_by=other_teacher,
        )
        self.client.force_login(teacher)

        response = self.client.get(reverse('library:teacher_resource_workspace'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Visible Teacher Notes')
        self.assertNotContains(response, 'Hidden Teacher Notes')

    def test_student_cannot_access_teacher_resource_workspace(self):
        student = User.objects.create_user(
            email='resource-denied-student@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )
        self.client.force_login(student)

        response = self.client.get(reverse('library:teacher_resource_workspace'))

        self.assertEqual(response.status_code, 403)

    def test_teacher_can_upload_learning_resource(self):
        teacher = User.objects.create_user(
            email='resource-upload-teacher@example.com',
            password='password123',
            first_name='Upload',
            last_name='Teacher',
            user_type=User.UserType.TEACHER,
        )
        self.client.force_login(teacher)

        response = self.client.post(
            reverse('library:teacher_resource_upload'),
            data={
                'title': 'Uploaded Teacher Resource',
                'description': 'Teacher uploaded resource',
                'resource_type': 'pdf',
                'author': 'Upload Teacher',
                'subject': 'Science',
                'grade_level': '10',
                'tags': '',
                'access_level': 'students',
                'is_downloadable': 'on',
                'file': SimpleUploadedFile('uploaded.pdf', b'%PDF-1.4', content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 302)
        resource = DigitalResource.objects.get(title='Uploaded Teacher Resource')
        self.assertEqual(resource.uploaded_by, teacher)
