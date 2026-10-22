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


class LibraryReportRegressionTests(TestCase):
    """F-35: the report panels had no endpoint to call."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='reports-admin@example.com',
            password='password123',
            first_name='Report',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        self.category = BookCategory.objects.create(name='Science')
        self.book = Book.objects.create(
            title='Biology for Secondary Schools',
            author='Teacher',
            isbn='9780000000001',
            category=self.category,
            availability='available',
        )
        self.client.force_login(self.admin)

    def test_reports_page_renders(self):
        response = self.client.get(reverse('library:reports'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Library')

    def test_generate_report_returns_json_payload(self):
        response = self.client.get(
            reverse('library:report_generate'),
            {'report_type': 'borrowing_summary', 'date_range': '30'},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['total_borrowings'], 0)
        self.assertIn('active_borrowings', payload)

    def test_generate_report_supports_every_declared_report_type(self):
        report_types = [
            'borrowing_summary', 'overdue_books', 'popular_books', 'user_activity',
            'inventory_status', 'fines_revenue', 'digital_resources', 'reservations',
            'monthly_stats',
        ]

        for report_type in report_types:
            with self.subTest(report_type=report_type):
                response = self.client.get(
                    reverse('library:report_generate'),
                    {'report_type': report_type, 'date_range': '30'},
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])

    def test_generate_report_rejects_unknown_report_type(self):
        response = self.client.get(
            reverse('library:report_generate'),
            {'report_type': 'does-not-exist'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_export_report_returns_csv(self):
        response = self.client.get(
            reverse('library:report_export'),
            {'report_type': 'inventory_status', 'format': 'csv'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_export_report_returns_excel(self):
        response = self.client.get(
            reverse('library:report_export'),
            {'report_type': 'inventory_status', 'format': 'excel'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

    def test_export_report_returns_pdf(self):
        response = self.client.get(
            reverse('library:report_export'),
            {'report_type': 'inventory_status', 'format': 'pdf'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_report_endpoints_require_admin(self):
        teacher = User.objects.create_user(
            email='reports-teacher@example.com',
            password='password123',
            user_type=User.UserType.TEACHER,
        )
        self.client.force_login(teacher)

        response = self.client.get(
            reverse('library:report_generate'),
            {'report_type': 'inventory_status'},
        )

        self.assertEqual(response.status_code, 403)


class LibraryLookupRegressionTests(TestCase):
    """F-56: the user lookup behind the reservation form had no endpoint."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='lookup-admin@example.com',
            password='password123',
            first_name='Lookup',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        self.student = User.objects.create_user(
            email='lookup-student@example.com',
            password='password123',
            first_name='student',
            last_name='banda',
            user_type=User.UserType.STUDENT,
        )
        self.category = BookCategory.objects.create(name='Fiction')
        self.book = Book.objects.create(
            title='The Long Walk',
            author='Author',
            isbn='9780000000002',
            category=self.category,
            barcode='BC-001',
        )
        self.client.force_login(self.admin)

    def test_user_search_matches_the_displayed_full_name(self):
        response = self.client.get(reverse('library:search_users'), {'q': 'student banda'})

        self.assertEqual(response.status_code, 200)
        users = response.json()['users']
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['id'], self.student.id)
        self.assertEqual(users[0]['full_name'], 'student banda')

    def test_user_search_returns_the_fields_used_by_the_form(self):
        response = self.client.get(reverse('library:search_users'), {'q': 'banda'})

        payload = response.json()['users'][0]
        for key in ('id', 'first_name', 'last_name', 'full_name', 'username', 'user_type'):
            self.assertIn(key, payload)

    def test_book_search_matches_title(self):
        response = self.client.get(reverse('library:search_books'), {'q': 'Long Walk'})

        self.assertEqual(response.status_code, 200)
        books = response.json()['books']
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]['id'], self.book.id)
        self.assertTrue(books[0]['is_available'])
        self.assertEqual(books[0]['available_copies'], 1)
        self.assertEqual(books[0]['total_copies'], 1)

    def test_book_details_endpoint_returns_the_book(self):
        response = self.client.get(
            reverse('library:book_details', kwargs={'pk': self.book.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['book']['title'], 'The Long Walk')

    def test_user_details_endpoint_returns_the_user(self):
        response = self.client.get(
            reverse('library:user_details', kwargs={'pk': self.student.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['user']['id'], self.student.id)

    def test_queue_info_endpoint_reports_the_reservation_queue(self):
        response = self.client.get(
            reverse('library:book_queue_info', kwargs={'pk': self.book.id})
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['queue_length'], 0)

    def test_user_search_is_not_available_to_students(self):
        student = User.objects.create_user(
            email='lookup-denied@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )
        self.client.force_login(student)

        response = self.client.get(reverse('library:search_users'), {'q': 'banda'})

        self.assertEqual(response.status_code, 403)


class LibraryBarcodeRegressionTests(TestCase):
    """The scanner page calls JSON endpoints that did not exist."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='barcode-admin@example.com',
            password='password123',
            first_name='Barcode',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        self.category = BookCategory.objects.create(name='Fiction')
        self.book = Book.objects.create(
            title='Scanned Book',
            author='Author',
            isbn='9780000000003',
            category=self.category,
            barcode='BC-002',
        )
        self.client.force_login(self.admin)

    def test_barcode_lookup_returns_json(self):
        response = self.client.get(reverse('library:barcode_scan'), {'barcode': 'BC-002'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['book']['id'], self.book.id)

    def test_barcode_lookup_reports_unknown_barcode(self):
        response = self.client.get(reverse('library:barcode_scan'), {'barcode': 'NOPE'})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])

    def test_barcode_scan_page_still_renders(self):
        response = self.client.get(reverse('library:barcode_scan'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Barcode Scanner')

    def test_identify_endpoint_detects_a_book(self):
        response = self.client.get(reverse('library:barcode_scan_identify'), {'barcode': 'BC-002'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['type'], 'book')
        self.assertEqual(payload['id'], self.book.id)

    def test_identify_endpoint_detects_a_user(self):
        user = User.objects.create_user(
            email='barcode-user@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )

        response = self.client.get(
            reverse('library:barcode_scan_identify'), {'barcode': 'barcode-user@example.com'}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['type'], 'user')
        self.assertEqual(payload['id'], user.id)

    def test_user_barcode_endpoint_returns_the_user(self):
        user = User.objects.create_user(
            email='barcode-user2@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )

        response = self.client.get(
            reverse('library:barcode_scan_user'), {'barcode': 'barcode-user2@example.com'}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['user']['id'], user.id)

    def test_return_lookup_reports_when_there_is_no_borrowing(self):
        response = self.client.get(
            reverse('library:barcode_scan_return'), {'barcode': 'BC-002'}
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])


class LibraryCategoryRegressionTests(TestCase):
    """F-49: Add Book required a category the form could not offer."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='category-admin@example.com',
            password='password123',
            first_name='Category',
            last_name='Admin',
            user_type=User.UserType.ADMINISTRATOR,
        )
        self.client.force_login(self.admin)

    def test_book_form_allows_creating_the_first_category(self):
        response = self.client.post(
            reverse('library:book_create'),
            data={
                'title': 'New Category Book',
                'author': 'Author',
                'isbn': '9780000000004',
                'new_category': 'History',
                'edition': '',
                'publisher': '',
                'publication_year': '',
                'pages': '',
                'description': '',
                'location': '',
                'availability': 'available',
                'condition': 'good',
                'price': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(title='New Category Book')
        self.assertEqual(book.category.name, 'History')

    def test_book_form_still_accepts_an_existing_category(self):
        category = BookCategory.objects.create(name='Science')

        response = self.client.post(
            reverse('library:book_create'),
            data={
                'title': 'Existing Category Book',
                'author': 'Author',
                'isbn': '9780000000005',
                'category': category.id,
                'new_category': '',
                'edition': '',
                'publisher': '',
                'publication_year': '',
                'pages': '',
                'description': '',
                'location': '',
                'availability': 'available',
                'condition': 'good',
                'price': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(title='Existing Category Book')
        self.assertEqual(book.category, category)

    def test_book_form_shows_the_new_category_field(self):
        response = self.client.get(reverse('library:book_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="new_category"')


class LibrarySummaryCounterRegressionTests(TestCase):
    """F-33: the summary counters rendered zero while a resource was listed."""

    def setUp(self):
        self.student = User.objects.create_user(
            email='counters-student@example.com',
            password='password123',
            user_type=User.UserType.STUDENT,
        )
        DigitalResource.objects.create(
            title='test',
            resource_type='pdf',
            file=SimpleUploadedFile('counter.pdf', b'%PDF-1.4'),
            access_level='students',
            current_downloads=3,
        )
        self.client.force_login(self.student)

    def test_digital_resource_list_reports_the_counters(self):
        response = self.client.get(reverse('library:digital_resource_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_resources'], 1)
        self.assertEqual(response.context['pdf_count'], 1)
        self.assertEqual(response.context['video_count'], 0)
        self.assertEqual(response.context['total_downloads'], 3)

    def test_book_list_reports_the_counters(self):
        category = BookCategory.objects.create(name='Science')
        Book.objects.create(
            title='Counted Book',
            author='Author',
            isbn='9780000000006',
            category=category,
            availability='available',
        )

        response = self.client.get(reverse('library:book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_books'], 1)
        self.assertEqual(response.context['available_books'], 1)
        self.assertEqual(response.context['borrowed_books'], 0)
        self.assertEqual(response.context['overdue_books'], 0)

