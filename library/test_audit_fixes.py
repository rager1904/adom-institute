"""Regression tests for the library audit.

Every test in this file pins down a defect that made a library flow
unusable, unsafe or misleading. They are deliberately small: each one fails
if the behaviour it guards regresses.
"""
from datetime import timedelta
import json

from accounts.models import Institution, InstitutionMembership
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import TagListField
from .models import (
    Book,
    BookBorrowing,
    BookCategory,
    BookReservation,
    LibrarySettings,
    ReturnRequest,
)

User = get_user_model()


class LibraryAuditMixin:
    """Shared fixtures for the audit tests."""

    def setUp(self):
        super().setUp()
        self.settings_row = LibrarySettings.get_settings()
        self.admin = self.make_user('audit-admin@example.com', User.UserType.ADMINISTRATOR)
        self.student = self.make_user('audit-student@example.com', User.UserType.STUDENT)
        self.other_student = self.make_user('audit-other@example.com', User.UserType.STUDENT)
        self.category = BookCategory.objects.create(name='Science')

    def make_user(self, email, user_type):
        return User.objects.create_user(
            email=email,
            password='password123',
            first_name='Audit',
            last_name=email.split('@')[0],
            user_type=user_type,
        )

    def make_book(self, title='Audited Book', availability='available', isbn=None):
        return Book.objects.create(
            title=title,
            author='A. Author',
            category=self.category,
            availability=availability,
            isbn=isbn,
        )

    def make_borrowing(self, user=None, due_in_days=14, returned=False):
        book = self.make_book(availability='borrowed' if not returned else 'available')
        return BookBorrowing.objects.create(
            book=book,
            borrower=user or self.student,
            due_date=timezone.now() + timedelta(days=due_in_days),
            return_date=timezone.now() if returned else None,
        )

    def make_overdue_borrowing(self, user=None, overdue_days=5):
        """A loan that is genuinely overdue.

        ``borrowed_date`` is ``auto_now_add`` and the table carries a
        ``due_date >= borrowed_date`` check constraint, so both columns are
        backdated together.
        """
        borrowing = self.make_borrowing(user=user)
        BookBorrowing.objects.filter(pk=borrowing.pk).update(
            borrowed_date=timezone.now() - timedelta(days=overdue_days + 14),
            due_date=timezone.now() - timedelta(days=overdue_days),
        )
        borrowing.refresh_from_db()
        return borrowing

    def make_reservation(self, user=None, book=None, status='pending'):
        return BookReservation.objects.create(
            book=book or self.make_book(),
            user=user or self.student,
            expiry_date=timezone.now() + timedelta(hours=48),
            status=status,
        )


class LibraryStatisticsApiTests(LibraryAuditMixin, TestCase):
    """The statistics endpoints used to raise NameError / 404."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_statistics_list_route_answers(self):
        response = self.client.get('/api/v1/library/statistics/')

        self.assertEqual(response.status_code, 200)

    def test_user_activity_endpoint_answers(self):
        response = self.client.get('/api/v1/library/statistics/user_activity/')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('user', payload)
        self.assertEqual(payload['user']['email'], self.admin.email)

    def test_dashboard_endpoint_answers(self):
        response = self.client.get('/api/v1/library/statistics/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('total_books', response.json())


class ReturnRequestExpiryTests(LibraryAuditMixin, TestCase):
    """Open return requests must not be cancelled just by looking at a page."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_open_return_request_survives_the_borrowings_page(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing,
            user=self.student,
            return_method='dropoff',
            status='approved',
        )

        response = self.client.get(reverse('library:borrowing_list'))

        self.assertEqual(response.status_code, 200)
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'approved')

    def test_return_request_lapses_after_the_pickup_window(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing,
            user=self.student,
            return_method='dropoff',
            status='approved',
        )
        stale = timezone.now() - timedelta(
            hours=self.settings_row.reservation_duration_hours + 1
        )
        ReturnRequest.objects.filter(pk=return_request.pk).update(requested_at=stale)

        self.client.get(reverse('library:borrowing_list'))

        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'cancelled')


class ReturnBookAvailabilityTests(LibraryAuditMixin, TestCase):
    """A returned book must respect a live reservation."""

    def test_returning_a_book_with_a_live_request_keeps_it_reserved(self):
        borrowing = self.make_borrowing()
        self.make_reservation(book=borrowing.book, status='pending')

        borrowing.return_book(returned_by=self.admin)

        borrowing.book.refresh_from_db()
        self.assertEqual(borrowing.book.availability, 'reserved')

    def test_returning_a_book_without_a_request_puts_it_back_on_the_shelf(self):
        borrowing = self.make_borrowing()

        borrowing.return_book(returned_by=self.admin)

        borrowing.book.refresh_from_db()
        self.assertEqual(borrowing.book.availability, 'available')

    def test_returning_a_book_with_a_closed_request_puts_it_back_on_the_shelf(self):
        borrowing = self.make_borrowing()
        self.make_reservation(book=borrowing.book, status='fulfilled')

        borrowing.return_book(returned_by=self.admin)

        borrowing.book.refresh_from_db()
        self.assertEqual(borrowing.book.availability, 'available')


class LateFeeTests(LibraryAuditMixin, TestCase):
    """The desk rate and the reported rate must be the same number."""

    def test_late_fee_uses_the_configured_daily_rate(self):
        LibrarySettings.objects.update_or_create(
            pk=self.settings_row.pk, defaults={'late_fee_per_day': 2.00},
        )
        borrowing = self.make_overdue_borrowing(overdue_days=5)

        self.assertEqual(borrowing.calculated_late_fee, 10.00)

    def test_late_fee_is_stored_when_the_book_comes_back(self):
        LibrarySettings.objects.update_or_create(
            pk=self.settings_row.pk, defaults={'late_fee_per_day': 2.00},
        )
        borrowing = self.make_overdue_borrowing(overdue_days=5)

        borrowing.return_book(returned_by=self.admin)

        borrowing.refresh_from_db()
        self.assertEqual(borrowing.late_fee, 10.00)

    def test_a_book_that_is_not_overdue_has_no_late_fee(self):
        borrowing = self.make_borrowing(due_in_days=5)

        self.assertEqual(borrowing.calculated_late_fee, 0)


class ReservationApiOwnershipTests(LibraryAuditMixin, TestCase):
    """A member must not raise or move a request for somebody else."""

    def test_student_cannot_raise_a_request_for_another_member(self):
        self.client.force_login(self.student)

        response = self.client.post(
            '/api/v1/library/reservations/',
            {
                'book_id': self.make_book().pk,
                'user_id': self.other_student.pk,
                'expiry_date': (timezone.now() + timedelta(hours=24)).isoformat(),
            },
        )

        self.assertIn(response.status_code, (200, 201))
        reservation = BookReservation.objects.latest('id')
        self.assertEqual(reservation.user, self.student)

    def test_student_cannot_move_a_request_to_another_member(self):
        reservation = self.make_reservation(user=self.student)
        self.client.force_login(self.student)

        response = self.client.patch(
            f'/api/v1/library/reservations/{reservation.pk}/',
            data=json.dumps({'user_id': self.other_student.pk}),
            content_type='application/json',
        )

        self.assertIn(response.status_code, (200, 400))
        reservation.refresh_from_db()
        self.assertEqual(reservation.user, self.student)


class ReturnRequestApiOwnershipTests(LibraryAuditMixin, TestCase):
    """A member must not request a return for somebody else's book."""

    def test_student_cannot_request_a_return_for_another_members_book(self):
        borrowing = self.make_borrowing(user=self.other_student)
        self.client.force_login(self.student)

        response = self.client.post(
            '/api/v1/library/return-requests/',
            {
                'borrowing_id': borrowing.pk,
                'return_method': 'dropoff',
                'delivery_address': 'Hostel',
                'delivery_phone': '0700000000',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReturnRequest.objects.exists())


class CatalogueFilterTests(LibraryAuditMixin, TestCase):
    """The catalogue filters have to reach the queryset."""

    def setUp(self):
        super().setUp()
        self.other_category = BookCategory.objects.create(name='History')
        self.available = self.make_book(title='Readable Book')
        self.borrowed = self.make_book(title='Out Book', availability='borrowed')
        self.history = Book.objects.create(
            title='Ancient Book',
            author='A. Author',
            category=self.other_category,
            availability='available',
        )
        self.client.force_login(self.admin)

    def test_catalogue_can_be_filtered_by_category(self):
        response = self.client.get(
            reverse('library:book_list'), {'category': self.category.pk},
        )

        self.assertEqual(response.status_code, 200)
        titles = [book.title for book in response.context['books']]
        self.assertIn(self.available.title, titles)
        self.assertNotIn(self.history.title, titles)

    def test_catalogue_can_be_filtered_by_availability(self):
        response = self.client.get(
            reverse('library:book_list'), {'status': 'borrowed'},
        )

        self.assertEqual(response.status_code, 200)
        titles = [book.title for book in response.context['books']]
        self.assertIn(self.borrowed.title, titles)
        self.assertNotIn(self.available.title, titles)

    def test_catalogue_renders_the_copy_counters(self):
        response = self.client.get(reverse('library:book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_books'], 3)
        self.assertEqual(response.context['available_books'], 2)


class BorrowingListFilterTests(LibraryAuditMixin, TestCase):
    """The borrowing list filters have to reach the queryset."""

    def setUp(self):
        super().setUp()
        self.overdue = self.make_overdue_borrowing(overdue_days=2)
        self.current = self.make_borrowing(due_in_days=10)
        self.client.force_login(self.admin)

    def test_borrowings_can_be_filtered_by_overdue_status(self):
        response = self.client.get(
            reverse('library:borrowing_list'), {'status': 'overdue'},
        )

        self.assertEqual(response.status_code, 200)
        ids = [borrowing.pk for borrowing in response.context['borrowings']]
        self.assertIn(self.overdue.pk, ids)
        self.assertNotIn(self.current.pk, ids)

    def test_borrowings_can_be_searched_by_book_title(self):
        response = self.client.get(
            reverse('library:borrowing_list'), {'search': self.overdue.book.title},
        )

        self.assertEqual(response.status_code, 200)
        ids = [borrowing.pk for borrowing in response.context['borrowings']]
        self.assertIn(self.overdue.pk, ids)

    def test_a_student_only_sees_their_own_borrowings(self):
        other = self.make_borrowing(user=self.other_student)
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:borrowing_list'))

        self.assertEqual(response.status_code, 200)
        ids = [borrowing.pk for borrowing in response.context['borrowings']]
        self.assertNotIn(other.pk, ids)


class LibrarySettingsPageTests(LibraryAuditMixin, TestCase):
    """The settings page used to post to an endpoint that did not exist."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_settings_page_renders_the_real_form(self):
        response = self.client.get(reverse('library:settings'))

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        for field in (
            'max_books_per_user',
            'borrowing_duration_days',
            'late_fee_per_day',
            'max_reservations_per_user',
            'reservation_duration_hours',
            'require_approval',
            'enable_delivery',
        ):
            self.assertIn(field, form.fields)

    def test_settings_page_saves_the_real_settings(self):
        response = self.client.post(
            reverse('library:settings'),
            {
                'max_books_per_user': 3,
                'borrowing_duration_days': 10,
                'late_fee_per_day': '1.50',
                'max_reservations_per_user': 2,
                'reservation_duration_hours': 24,
                'require_approval': 'on',
                'enable_delivery': 'on',
                'enable_barcode': 'on',
                'enable_qr_code': 'on',
                'enable_digital_resources': 'on',
                'enable_reservations': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.settings_row.refresh_from_db()
        self.assertEqual(self.settings_row.max_books_per_user, 3)
        self.assertEqual(self.settings_row.late_fee_per_day, 1.50)
        self.assertTrue(self.settings_row.require_approval)
        self.assertTrue(self.settings_row.enable_delivery)

    def test_a_student_cannot_open_the_settings_page(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:settings'))

        self.assertEqual(response.status_code, 302)


class ReservationListPageTests(LibraryAuditMixin, TestCase):
    """The request list used to render fields the model does not have."""

    def test_request_list_renders_for_a_student(self):
        reservation = self.make_reservation(user=self.student)
        self.client.force_login(self.student)

        response = self.client.get(reverse('library:reservation_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reservation.book.title)
        self.assertEqual(list(response.context['reservations']), [reservation])

    def test_request_list_offers_staff_the_review_queue(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('library:reservation_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_review'])

    def test_request_list_can_be_filtered_by_status(self):
        pending = self.make_reservation(user=self.student, status='pending')
        self.make_reservation(user=self.student, status='fulfilled')
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('library:reservation_list'), {'status': 'active'},
        )

        self.assertEqual(response.status_code, 200)
        ids = [reservation.pk for reservation in response.context['reservations']]
        self.assertIn(pending.pk, ids)
        self.assertEqual(len(ids), 1)


class ReturnRequestFormTests(LibraryAuditMixin, TestCase):
    """A student has to be able to pick the book they are handing back."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_return_page_offers_the_books_the_member_holds(self):
        borrowing = self.make_borrowing()

        response = self.client.get(reverse('library:return_request_create'))

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('borrowing', form.fields)
        self.assertEqual(
            list(form.fields['borrowing'].queryset.values_list('pk', flat=True)),
            [borrowing.pk],
        )

    def test_return_page_hides_the_picker_when_the_book_is_fixed(self):
        borrowing = self.make_borrowing()

        response = self.client.get(
            reverse('library:return_request_create_for', args=[borrowing.pk]),
        )

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.fields['borrowing'].required)
        self.assertTrue(form.fields['borrowing'].widget.is_hidden)

    def test_return_request_can_be_raised_by_choosing_the_book(self):
        borrowing = self.make_borrowing()

        response = self.client.post(
            reverse('library:return_request_create'),
            {
                'borrowing': borrowing.pk,
                'return_method': 'dropoff',
                'delivery_address': 'Hostel block B',
                'delivery_phone': '0700000000',
            },
        )

        self.assertEqual(response.status_code, 302)
        return_request = ReturnRequest.objects.latest('id')
        self.assertEqual(return_request.borrowing, borrowing)
        self.assertEqual(return_request.user, self.student)
        self.assertEqual(return_request.status, 'pending')

    def test_return_request_is_rejected_for_a_book_the_member_does_not_hold(self):
        other = self.make_borrowing(user=self.other_student)

        response = self.client.post(
            reverse('library:return_request_create'),
            {
                'borrowing': other.pk,
                'return_method': 'dropoff',
                'delivery_address': 'Hostel block B',
                'delivery_phone': '0700000000',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReturnRequest.objects.exists())


class StaffFormRenderingTests(LibraryAuditMixin, TestCase):
    """The staff forms have to render the fields the form actually has."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_borrowing_form_renders_the_borrower_picker(self):
        response = self.client.get(reverse('library:borrowing_create'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('borrower', response.context['form'].fields)
        self.assertContains(response, 'id_borrower')

    def test_a_librarian_can_lend_a_book_through_the_web_form(self):
        book = self.make_book()

        response = self.client.post(
            reverse('library:borrowing_create'),
            {
                'book': book.pk,
                'borrower': self.student.pk,
                'due_date': (timezone.now() + timedelta(days=14)).strftime(
                    '%Y-%m-%d %H:%M'
                ),
                'fulfillment_method': 'pickup',
                'delivery_address': '',
                'notes': 'For the term project.',
            },
        )

        self.assertEqual(response.status_code, 302)
        borrowing = BookBorrowing.objects.latest('id')
        self.assertEqual(borrowing.book, book)
        self.assertEqual(borrowing.borrower, self.student)
        self.assertEqual(borrowing.fulfillment_method, 'pickup')
        book.refresh_from_db()
        self.assertEqual(book.availability, 'borrowed')

    def test_a_delivered_loan_needs_an_address(self):
        book = self.make_book()

        response = self.client.post(
            reverse('library:borrowing_create'),
            {
                'book': book.pk,
                'borrower': self.student.pk,
                'due_date': (timezone.now() + timedelta(days=14)).strftime(
                    '%Y-%m-%d %H:%M'
                ),
                'fulfillment_method': 'delivery',
                'delivery_address': '',
                'notes': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'delivery_address', response.context['form'].errors,
        )
        self.assertFalse(BookBorrowing.objects.exists())

    def test_reservation_form_renders_the_collection_method(self):
        self.make_book(availability='borrowed')

        response = self.client.get(reverse('library:reservation_create'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('fulfillment_method', response.context['form'].fields)
        self.assertContains(response, 'id_fulfillment_method')

    def test_a_librarian_can_raise_a_request_through_the_web_form(self):
        book = self.make_book(availability='borrowed')

        response = self.client.post(
            reverse('library:reservation_create'),
            {
                'book': book.pk,
                'user': self.student.pk,
                'fulfillment_method': 'pickup',
                'delivery_address': '',
                'delivery_phone': '',
                'notes': 'Waiting for it.',
            },
        )

        self.assertEqual(response.status_code, 302)
        reservation = BookReservation.objects.latest('id')
        self.assertEqual(reservation.book, book)
        self.assertEqual(reservation.user, self.student)
        self.assertEqual(reservation.fulfillment_method, 'pickup')
        self.assertIsNotNone(reservation.expiry_date)

    def test_book_form_renders_the_real_book_fields(self):
        response = self.client.get(reverse('library:book_create'))

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        for field in ('availability', 'condition', 'price', 'is_active'):
            self.assertIn(field, form.fields)

    def test_book_form_does_not_offer_fields_the_model_does_not_have(self):
        response = self.client.get(reverse('library:book_create'))

        form = response.context['form']
        for field in ('total_copies', 'tags', 'language'):
            self.assertNotIn(field, form.fields)


class BulkImportTests(LibraryAuditMixin, TestCase):
    """One bad row must not throw away the whole import."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def upload(self, body, encoding='utf-8'):
        upload = SimpleUploadedFile(
            'books.csv', body.encode(encoding) if isinstance(body, str) else body,
            content_type='text/csv',
        )
        return self.client.post(reverse('library:bulk_import'), {'csv_file': upload})

    def test_a_good_row_is_imported(self):
        response = self.upload(
            'title,author,category,isbn\n'
            'Dune,Frank Herbert,Science,9780441013593\n'
        )

        self.assertEqual(response.status_code, 302)
        book = Book.objects.get(isbn='9780441013593')
        self.assertEqual(book.title, 'Dune')
        self.assertEqual(book.category.name, 'Science')

    def test_a_bad_row_is_skipped_and_the_rest_is_imported(self):
        response = self.upload(
            'title,author,category\n'
            'Dune,Frank Herbert,Science\n'
            ',Missing Author,Science\n'
            'Another,,Science\n'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(len(response.context['import_errors']), 2)
        self.assertContains(response, 'a title and an author are required')

    def test_a_duplicate_isbn_is_skipped(self):
        self.make_book(title='Existing', isbn='9780441013593')

        response = self.upload(
            'title,author,isbn\n'
            'Dune,Frank Herbert,9780441013593\n'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Book.objects.count(), 1)
        self.assertContains(response, 'already in the catalogue')

    def test_a_row_without_a_category_lands_in_uncategorised(self):
        self.upload('title,author\nDune,Frank Herbert\n')

        book = Book.objects.get(title='Dune')
        self.assertEqual(book.category.name, 'Uncategorised')

    def test_unreadable_numbers_do_not_kill_the_import(self):
        self.upload(
            'title,author,publication_year,pages,price\n'
            'Dune,Frank Herbert,unknown,not a number,free\n'
        )

        book = Book.objects.get(title='Dune')
        self.assertIsNone(book.publication_year)
        self.assertIsNone(book.pages)
        self.assertIsNone(book.price)

    def test_a_spreadsheet_export_that_is_not_utf8_is_still_read(self):
        response = self.upload(
            'title,author\nDune,Frank Herbert\n', encoding='cp1252',
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Book.objects.filter(title='Dune').exists())


class AdminPermissionConsistencyTests(LibraryAuditMixin, TestCase):
    """An institution owner is an administrator everywhere, not just sometimes."""

    def setUp(self):
        super().setUp()
        self.institution = Institution.objects.create(
            name='Audit School',
            code='AUDIT-SCHOOL',
            status=Institution.Status.APPROVED,
        )
        self.owner = self.make_user('audit-owner@example.com', User.UserType.TEACHER)
        InstitutionMembership.objects.create(
            institution=self.institution,
            user=self.owner,
            role=InstitutionMembership.MembershipRole.OWNER,
        )
        self.plain_teacher = self.make_user(
            'audit-teacher@example.com', User.UserType.TEACHER,
        )

    def test_an_institution_owner_can_reach_the_staff_pages(self):
        self.client.force_login(self.owner)

        for url in ('library:book_create', 'library:borrowing_create', 'library:reservation_create'):
            response = self.client.get(reverse(url))
            self.assertEqual(response.status_code, 200, url)

    def test_a_teacher_without_the_role_is_still_refused(self):
        self.client.force_login(self.plain_teacher)

        response = self.client.get(reverse('library:book_create'))

        self.assertIn(response.status_code, (302, 403))


class TagListFieldTests(TestCase):
    """The tag field used to render a hidden "False" input."""

    def test_tag_field_does_not_render_a_hidden_false_input(self):
        field = TagListField(required=False)

        rendered = str(field)

        self.assertNotIn('value="False"', rendered)
