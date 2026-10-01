"""Learning material is read-only: viewable inline, never downloadable."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from adom.protected_media import is_protected_media_path
from .models import DigitalResource

PDF_BYTES = b'%PDF-1.4 read-only lesson material'


def make_user(email, user_type, **extra):
    return User.objects.create_user(
        email=email,
        password='password123',
        user_type=getattr(User.UserType, user_type.upper()),
        **extra,
    )


class ProtectedMediaPathTests(TestCase):
    """The raw /media/ route must never expose material."""

    def test_material_directories_are_protected(self):
        for path in (
            'library/digital/abc.pdf',
            'assignments/brief.docx',
            'assignment_submissions/homework.pdf',
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected_media_path(path))

    def test_non_material_directories_are_served_normally(self):
        for path in ('avatars/user.png', 'library/covers/cover.jpg', 'subjects/icon.png'):
            with self.subTest(path=path):
                self.assertFalse(is_protected_media_path(path))

    def test_raw_media_url_for_material_returns_404(self):
        student = make_user('raw-media-student@example.com', 'student')
        resource = DigitalResource.objects.create(
            title='Guarded PDF',
            resource_type='pdf',
            file=SimpleUploadedFile('guarded.pdf', PDF_BYTES),
            access_level='students',
        )
        self.client.force_login(student)

        response = self.client.get(f'/media/{resource.file.name}')

        self.assertEqual(response.status_code, 404)


class DigitalResourceInlineViewTests(TestCase):
    def setUp(self):
        self.student = make_user('inline-student@example.com', 'student')
        self.other_student = make_user('inline-other-student@example.com', 'student')
        self.teacher = make_user('inline-teacher@example.com', 'teacher')
        self.resource = DigitalResource.objects.create(
            title='Read Only Lesson',
            resource_type='pdf',
            file=SimpleUploadedFile('lesson.pdf', PDF_BYTES),
            access_level='students',
            is_downloadable=True,
        )

    def test_viewer_requires_sign_in(self):
        response = self.client.get(reverse('library:resource_file', args=[self.resource.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_viewer_streams_inline_and_forbids_caching(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:resource_file', args=[self.resource.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), PDF_BYTES)
        self.assertTrue(response['Content-Disposition'].startswith('inline;'))
        self.assertNotIn('attachment', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_viewer_records_a_view_not_a_download(self):
        self.client.force_login(self.student)

        self.client.get(reverse('library:resource_file', args=[self.resource.pk]))

        self.assertEqual(self.resource.access_logs.filter(action='view').count(), 1)
        self.assertEqual(self.resource.access_logs.filter(action='download').count(), 0)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.current_downloads, 0)

    def test_viewer_supports_range_requests_for_media_seeking(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library:resource_file', args=[self.resource.pk]),
            HTTP_RANGE='bytes=5-9',
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(b''.join(response.streaming_content), PDF_BYTES[5:10])
        self.assertEqual(
            response['Content-Range'],
            f'bytes 5-9/{len(PDF_BYTES)}',
        )

    def test_viewer_rejects_an_unsatisfiable_range(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library:resource_file', args=[self.resource.pk]),
            HTTP_RANGE='bytes=99999-',
        )

        self.assertEqual(response.status_code, 416)

    def test_student_cannot_read_teacher_only_material(self):
        teacher_only = DigitalResource.objects.create(
            title='Teacher Only Notes',
            resource_type='pdf',
            file=SimpleUploadedFile('teacher-only.pdf', PDF_BYTES),
            access_level='teachers',
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:resource_file', args=[teacher_only.pk]))

        self.assertEqual(response.status_code, 403)

    def test_teacher_can_read_teacher_only_material(self):
        teacher_only = DigitalResource.objects.create(
            title='Teacher Only Notes',
            resource_type='pdf',
            file=SimpleUploadedFile('teacher-only.pdf', PDF_BYTES),
            access_level='teachers',
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse('library:resource_file', args=[teacher_only.pk]))

        self.assertEqual(response.status_code, 200)

    def test_detail_page_hides_teacher_material_from_students(self):
        teacher_only = DigitalResource.objects.create(
            title='Hidden Teacher Notes',
            resource_type='pdf',
            file=SimpleUploadedFile('hidden.pdf', PDF_BYTES),
            access_level='teachers',
        )
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library:digital_resource_detail', args=[teacher_only.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_download_route_refuses_while_downloads_are_disabled(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:download_resource', args=[self.resource.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('library:digital_resource_detail', args=[self.resource.pk]))
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.current_downloads, 0)

    @override_settings(ALLOW_MATERIAL_DOWNLOADS=True)
    def test_download_route_serves_attachment_when_explicitly_enabled(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:download_resource', args=[self.resource.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('attachment;'))


class DigitalResourceWriteAccessTests(TestCase):
    """Material is read-only for everyone except admins and teachers."""

    def setUp(self):
        self.student = make_user('write-student@example.com', 'student')
        self.teacher = make_user('write-teacher@example.com', 'teacher')
        self.resource = DigitalResource.objects.create(
            title='Locked Down Material',
            resource_type='pdf',
            file=SimpleUploadedFile('locked.pdf', PDF_BYTES),
            access_level='students',
        )

    def test_student_cannot_open_the_create_form(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:digital_resource_create'))

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_edit_material(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library:digital_resource_update', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_delete_material(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library:digital_resource_delete', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(DigitalResource.objects.filter(pk=self.resource.pk).exists())

    def test_teacher_can_open_the_create_form(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse('library:digital_resource_create'))

        self.assertEqual(response.status_code, 200)

    def test_edit_form_never_renders_the_raw_file_url(self):
        # A teacher only sees their own uploads, so the resource under test is
        # owned by the teacher doing the editing.
        owned = DigitalResource.objects.create(
            title='Owned Material',
            resource_type='pdf',
            file=SimpleUploadedFile('owned.pdf', PDF_BYTES),
            access_level='students',
            uploaded_by=self.teacher,
        )
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse('library:digital_resource_update', args=[owned.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            f'/media/{owned.file.name}',
            response.content.decode(),
        )

    def test_detail_page_offers_the_protected_viewer_not_raw_media(self):
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse('library:digital_resource_detail', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(reverse('library:resource_file', args=[self.resource.pk]), body)
        self.assertNotIn(f'/media/{self.resource.file.name}', body)

    def test_teacher_cannot_edit_another_teachers_material(self):
        other_teacher = make_user('write-other-teacher@example.com', 'teacher')
        self.client.force_login(other_teacher)

        response = self.client.get(
            reverse('library:digital_resource_update', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_api_refuses_student_writes(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('library_api:digitalresource-list'),
            data={'title': 'Sneaky Upload'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(DigitalResource.objects.filter(title='Sneaky Upload').exists())

    def test_api_refuses_student_deletes(self):
        self.client.force_login(self.student)

        response = self.client.delete(
            reverse('library_api:digitalresource-detail', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(DigitalResource.objects.filter(pk=self.resource.pk).exists())

    def test_api_download_action_refuses_while_downloads_are_disabled(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse('library_api:digitalresource-download', args=[self.resource.pk]),
            data={'action': 'download'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.current_downloads, 0)

    def test_api_never_exposes_the_raw_file_url(self):
        self.client.force_login(self.student)

        response = self.client.get(
            reverse('library_api:digitalresource-detail', args=[self.resource.pk])
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn('file', payload)
        self.assertEqual(
            payload['file_url'],
            reverse('library:resource_file', args=[self.resource.pk]),
        )
        self.assertNotIn('/media/', response.content.decode())
