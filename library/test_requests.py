"""Tests for the student book-request and return-request flows.

Covers the two directions a student can initiate:

* request a book  -> staff approve (pickup or delivery) -> hand over
* request a return -> staff approve (drop off or courier) -> book checked in
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Book, BookBorrowing, BookCategory, BookReservation, LibrarySettings,
    ReturnRequest,
)

User = get_user_model()


def make_user(email, user_type):
    return User.objects.create_user(
        email=email,
        password='password123',
        user_type=getattr(User.UserType, user_type.upper()),
    )


class LibraryFlowMixin:
    def setUp(self):
        super().setUp()
        self.settings_row = LibrarySettings.get_settings()

        self.admin = make_user('flow-librarian@example.com', 'administrator')
        self.student = make_user('flow-student@example.com', 'student')
        self.other_student = make_user('flow-student2@example.com', 'student')
        self.category = BookCategory.objects.create(name='Science')

    def login_student(self, user=None):
        self.client.force_login(user or self.student)

    def login_admin(self):
        self.client.force_login(self.admin)

    def make_book(self, title='Principles of Biology', availability='available'):
        return Book.objects.create(
            title=title,
            author='A. Author',
            category=self.category,
            availability=availability,
        )

    def make_reservation(self, book=None, user=None, method='pickup', status='pending'):
        reservation = BookReservation.objects.create(
            book=book or self.make_book(),
            user=user or self.student,
            expiry_date=timezone.now() + timedelta(hours=48),
            fulfillment_method=method,
            status=status,
        )
        return reservation


class BookRequestTests(LibraryFlowMixin, TestCase):
    """A student asks for a book and staff approve it."""

    def test_student_submits_pickup_request_and_it_waits_for_staff(self):
        book = self.make_book()

        self.login_student()
        response = self.client.post(
            reverse('library:request_create'),
            {'book': book.pk, 'fulfillment_method': 'pickup', 'notes': ''},
        )

        self.assertRedirects(response, reverse('library:reservation_list'))
        reservation = BookReservation.objects.get()
        self.assertEqual(reservation.user, self.student)
        self.assertEqual(reservation.status, 'pending')
        self.assertEqual(reservation.fulfillment_method, 'pickup')
        # The book is not held until a librarian approves.
        book.refresh_from_db()
        self.assertEqual(book.availability, 'available')
        self.assertFalse(BookBorrowing.objects.exists())

    def test_student_requests_delivery_with_an_address(self):
        book = self.make_book()

        self.login_student()
        self.client.post(reverse('library:request_create'), {
            'book': book.pk,
            'fulfillment_method': 'delivery',
            'delivery_address': '12 Hostel Road, Accra',
            'delivery_phone': '0244000000',
        })

        reservation = BookReservation.objects.get()
        self.assertEqual(reservation.fulfillment_method, 'delivery')
        self.assertEqual(reservation.delivery_address, '12 Hostel Road, Accra')

    def test_delivery_request_without_an_address_is_rejected(self):
        book = self.make_book()

        self.login_student()
        response = self.client.post(reverse('library:request_create'), {
            'book': book.pk,
            'fulfillment_method': 'delivery',
            'delivery_address': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookReservation.objects.exists())
        self.assertContains(response, 'delivery address')

    def test_delivery_is_refused_when_the_library_disables_it(self):
        self.settings_row.enable_delivery = False
        self.settings_row.save()

        book = self.make_book()
        self.login_student()
        response = self.client.post(reverse('library:request_create'), {
            'book': book.pk,
            'fulfillment_method': 'delivery',
            'delivery_address': '12 Hostel Road',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookReservation.objects.exists())

    def test_student_cannot_request_the_same_book_twice(self):
        book = self.make_book()
        self.make_reservation(book=book)

        self.login_student()
        response = self.client.post(reverse('library:request_create'), {
            'book': book.pk, 'fulfillment_method': 'pickup',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BookReservation.objects.count(), 1)

    def test_request_count_is_capped_by_library_settings(self):
        self.settings_row.max_reservations_per_user = 2
        self.settings_row.save()

        for index in range(2):
            self.make_reservation(book=self.make_book(f'Book {index}'))

        self.login_student()
        response = self.client.post(reverse('library:request_create'), {
            'book': self.make_book('Book 3').pk, 'fulfillment_method': 'pickup',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BookReservation.objects.count(), 2)

    def test_staff_approval_holds_the_book_without_creating_a_loan(self):
        book = self.make_book()
        reservation = self.make_reservation(book=book)

        self.login_admin()
        self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'approve', 'fulfillment_method': 'pickup'},
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'approved')
        self.assertEqual(reservation.reviewed_by, self.admin)
        book.refresh_from_db()
        self.assertEqual(book.availability, 'reserved')
        self.assertFalse(BookBorrowing.objects.exists())

    def test_staff_can_override_the_fulfilment_method(self):
        book = self.make_book()
        reservation = self.make_reservation(book=book, method='delivery')
        reservation.delivery_address = '12 Hostel Road'
        reservation.save()

        self.login_admin()
        self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'approve', 'fulfillment_method': 'pickup'},
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.fulfillment_method, 'pickup')
        self.assertTrue(reservation.method_overridden)

    def test_rejection_requires_a_reason(self):
        reservation = self.make_reservation()

        self.login_admin()
        # A blank reason is refused, so the request stays open.
        self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'reject', 'staff_notes': '  '},
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')

        self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'reject', 'staff_notes': 'Not on the syllabus.'},
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'rejected')

    def test_rejection_frees_the_book(self):
        book = self.make_book()
        reservation = self.make_reservation(book=book)
        reservation.approve(reviewed_by=self.admin)
        book.refresh_from_db()
        self.assertEqual(book.availability, 'reserved')

        self.login_admin()
        self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'reject', 'staff_notes': 'Not on the syllabus.'},
        )

        reservation.refresh_from_db()
        book.refresh_from_db()
        self.assertEqual(reservation.status, 'rejected')
        self.assertEqual(book.availability, 'available')

    def test_handover_creates_the_loan_with_the_agreed_method(self):
        book = self.make_book()
        reservation = self.make_reservation(book=book, method='delivery')
        reservation.delivery_address = '12 Hostel Road'
        reservation.save()
        reservation.approve(reviewed_by=self.admin)

        self.login_admin()
        self.client.post(
            reverse('library:reservation_fulfil', args=[reservation.pk]),
            {'confirm': '1'},
        )

        borrowing = BookBorrowing.objects.get()
        self.assertEqual(borrowing.book, book)
        self.assertEqual(borrowing.borrower, self.student)
        self.assertEqual(borrowing.fulfillment_method, 'delivery')
        self.assertEqual(borrowing.delivery_address, '12 Hostel Road')
        self.assertGreater(borrowing.due_date, timezone.now())

        reservation.refresh_from_db()
        book.refresh_from_db()
        self.assertEqual(reservation.status, 'fulfilled')
        self.assertEqual(reservation.borrowing, borrowing)
        self.assertEqual(book.availability, 'borrowed')

    def test_a_student_cannot_approve_or_hand_over_their_own_request(self):
        reservation = self.make_reservation()

        self.login_student()
        response = self.client.post(
            reverse('library:reservation_decide', args=[reservation.pk]),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            reverse('library:reservation_fulfil', args=[reservation.pk]),
            {'confirm': '1'},
        )
        self.assertEqual(response.status_code, 302)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')
        self.assertFalse(BookBorrowing.objects.exists())

    def test_approval_can_be_turned_off_to_issue_immediately(self):
        self.settings_row.require_approval = False
        self.settings_row.save()

        book = self.make_book()
        self.login_student()
        self.client.post(reverse('library:request_create'), {
            'book': book.pk, 'fulfillment_method': 'pickup',
        })

        reservation = BookReservation.objects.get()
        self.assertEqual(reservation.status, 'fulfilled')
        borrowing = BookBorrowing.objects.get()
        self.assertEqual(borrowing.borrower, self.student)
        book.refresh_from_db()
        self.assertEqual(book.availability, 'borrowed')

    def test_lapsed_requests_expire_when_listed(self):
        book = self.make_book()
        reservation = self.make_reservation(book=book, status='available')
        # reservation_date is auto_now_add and expiry must be after it, so
        # backdate both to build a genuinely lapsed hold.
        BookReservation.objects.filter(pk=reservation.pk).update(
            reservation_date=timezone.now() - timedelta(days=3),
            expiry_date=timezone.now() - timedelta(hours=1),
        )

        self.login_admin()
        self.client.get(reverse('library:reservation_review'))

        reservation.refresh_from_db()
        book.refresh_from_db()
        self.assertEqual(reservation.status, 'expired')
        self.assertEqual(book.availability, 'available')

    def test_cancelling_a_request_is_a_staff_action(self):
        reservation = self.make_reservation()

        self.login_student(self.other_student)
        response = self.client.post(
            reverse('library:cancel_reservation', args=[reservation.pk])
        )
        self.assertEqual(response.status_code, 302)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, 'pending')


class ReturnRequestTests(LibraryFlowMixin, TestCase):
    """A student asks to hand a book back."""

    def make_borrowing(self, user=None, overdue_days=0):
        book = self.make_book(availability='borrowed')
        borrowing = BookBorrowing.objects.create(
            book=book,
            borrower=user or self.student,
            due_date=timezone.now() + timedelta(days=14),
        )
        if overdue_days:
            # borrowed_date is auto_now_add, so backdate both through the
            # queryset to build a genuinely overdue loan.
            BookBorrowing.objects.filter(pk=borrowing.pk).update(
                borrowed_date=timezone.now() - timedelta(days=overdue_days + 14),
                due_date=timezone.now() - timedelta(days=overdue_days),
            )
            borrowing.refresh_from_db()
        return borrowing

    def test_student_requests_a_drop_off_return(self):
        borrowing = self.make_borrowing()

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_create_for', args=[borrowing.pk]),
            {'return_method': 'dropoff', 'notes': 'Leaving it at the front desk.'},
        )

        self.assertRedirects(response, reverse('library:return_request_list'))
        return_request = ReturnRequest.objects.get()
        self.assertEqual(return_request.borrowing, borrowing)
        self.assertEqual(return_request.user, self.student)
        self.assertEqual(return_request.return_method, 'dropoff')
        self.assertEqual(return_request.status, 'pending')
        # Requesting a return does not close the loan.
        borrowing.refresh_from_db()
        self.assertIsNone(borrowing.return_date)

    def test_student_requests_a_courier_collection(self):
        borrowing = self.make_borrowing()

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_create_for', args=[borrowing.pk]), {
                'return_method': 'collection',
                'delivery_address': 'Room 14, Hostel B',
                'delivery_phone': '0244000000',
            }
        )

        self.assertEqual(response.status_code, 302)
        return_request = ReturnRequest.objects.get()
        self.assertEqual(return_request.return_method, 'collection')
        self.assertEqual(return_request.delivery_phone, '0244000000')

    def test_collection_without_an_address_or_phone_is_rejected(self):
        borrowing = self.make_borrowing()

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_create_for', args=[borrowing.pk]), {
                'return_method': 'collection',
                'delivery_address': '',
                'delivery_phone': '',
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReturnRequest.objects.exists())

    def test_cannot_request_a_return_for_someone_elses_book(self):
        self.make_borrowing(user=self.other_student)

        self.login_student()
        response = self.client.get(
            reverse('library:return_request_create_for',
                    args=[BookBorrowing.objects.get().pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_request_a_second_return_for_the_same_book(self):
        self.make_borrowing()
        ReturnRequest.objects.create(
            borrowing=BookBorrowing.objects.get(),
            user=self.student,
            return_method='dropoff',
        )

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_create_for', args=[BookBorrowing.objects.get().pk]),
            {'return_method': 'dropoff'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReturnRequest.objects.count(), 1)

    def test_cannot_return_a_book_that_is_already_back(self):
        borrowing = self.make_borrowing()
        borrowing.return_book(self.admin)

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_create_for', args=[borrowing.pk]),
            {'return_method': 'dropoff'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReturnRequest.objects.exists())

    def test_staff_approve_then_check_in_closes_the_loan(self):
        borrowing = self.make_borrowing(overdue_days=3)
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='collection',
            delivery_address='Room 14, Hostel B', delivery_phone='0244000000',
        )

        self.login_admin()

        self.client.post(
            reverse('library:return_request_decide', args=[return_request.pk]),
            {'action': 'approve', 'return_method': 'collection'},
        )
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'approved')

        self.client.post(reverse('library:return_request_transit', args=[return_request.pk]))
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'in_transit')

        self.client.post(
            reverse('library:return_request_receive', args=[return_request.pk]),
            {'condition': 'fair', 'return_notes': 'Cover is creased.'},
        )

        return_request.refresh_from_db()
        borrowing.refresh_from_db()
        borrowing.book.refresh_from_db()

        self.assertEqual(return_request.status, 'received')
        self.assertEqual(return_request.condition_on_receipt, 'fair')
        self.assertIsNotNone(borrowing.return_date)
        self.assertEqual(borrowing.returned_by, self.admin)
        self.assertGreater(borrowing.late_fee, 0)
        self.assertEqual(borrowing.book.availability, 'available')
        self.assertEqual(borrowing.book.condition, 'fair')

    def test_rejecting_a_return_keeps_the_loan_open(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff',
        )

        self.login_admin()
        self.client.post(
            reverse('library:return_request_decide', args=[return_request.pk]),
            {'action': 'reject', 'staff_notes': 'Please bring it to the counter.'},
        )

        return_request.refresh_from_db()
        borrowing.refresh_from_db()
        self.assertEqual(return_request.status, 'rejected')
        self.assertIn('counter', return_request.staff_notes)
        self.assertIsNone(borrowing.return_date)

    def test_rejection_requires_a_reason(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff',
        )

        self.login_admin()
        self.client.post(
            reverse('library:return_request_decide', args=[return_request.pk]),
            {'action': 'reject', 'staff_notes': '  '},
        )

        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'pending')

    def test_student_cannot_check_in_their_own_return(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff', status='approved',
        )

        self.login_student()
        response = self.client.post(
            reverse('library:return_request_receive', args=[return_request.pk])
        )
        self.assertEqual(response.status_code, 302)

        borrowing.refresh_from_db()
        self.assertIsNone(borrowing.return_date)

    def test_student_withdraws_their_own_return_request(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff',
        )

        self.login_student()
        self.client.post(reverse('library:cancel_return_request', args=[return_request.pk]))

        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'cancelled')

    def test_student_cannot_withdraw_someone_elses_request(self):
        borrowing = self.make_borrowing(user=self.other_student)
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.other_student, return_method='dropoff',
        )

        self.login_student()
        response = self.client.post(
            reverse('library:cancel_return_request', args=[return_request.pk])
        )
        self.assertEqual(response.status_code, 404)
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'pending')

    def test_desk_return_closes_a_pending_student_request(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff',
        )

        self.login_admin()
        response = self.client.post(
            reverse('library:return_book', args=[borrowing.pk]),
            {'return_notes': 'Handed over the counter.'},
        )
        self.assertRedirects(response, reverse('library:borrowing_list'))

        borrowing.refresh_from_db()
        return_request.refresh_from_db()
        self.assertIsNotNone(borrowing.return_date)
        self.assertEqual(return_request.status, 'received')
        self.assertEqual(return_request.received_by, self.admin)


class ReturnRequestApiTests(LibraryFlowMixin, TestCase):
    """The API must not let a student bypass the approval gate."""

    def make_borrowing(self, user=None):
        book = self.make_book(availability='borrowed')
        return BookBorrowing.objects.create(
            book=book, borrower=user or self.student,
            due_date=timezone.now() + timedelta(days=14),
        )

    def test_student_cannot_return_a_book_through_the_api(self):
        borrowing = self.make_borrowing()

        self.login_student()
        response = self.client.post(
            f'/api/v1/library/borrowings/{borrowing.pk}/return_book/',
            {'borrowing_id': borrowing.pk},
        )

        self.assertEqual(response.status_code, 403)
        borrowing.refresh_from_db()
        self.assertIsNone(borrowing.return_date)

    def test_student_only_sees_their_own_return_requests(self):
        mine = ReturnRequest.objects.create(
            borrowing=self.make_borrowing(), user=self.student, return_method='dropoff',
        )
        theirs = ReturnRequest.objects.create(
            borrowing=self.make_borrowing(user=self.other_student),
            user=self.other_student, return_method='dropoff',
        )

        self.login_student()
        response = self.client.get('/api/v1/library/return-requests/')
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        results = payload['results'] if isinstance(payload, dict) else payload
        ids = [item['id'] for item in results]
        self.assertIn(mine.pk, ids)
        self.assertNotIn(theirs.pk, ids)

    def test_student_cannot_decide_a_return_request(self):
        return_request = ReturnRequest.objects.create(
            borrowing=self.make_borrowing(), user=self.student, return_method='dropoff',
        )

        self.login_student()
        response = self.client.post(
            f'/api/v1/library/return-requests/{return_request.pk}/decide/',
            {'action': 'approve'},
        )

        self.assertEqual(response.status_code, 403)
        return_request.refresh_from_db()
        self.assertEqual(return_request.status, 'pending')

    def test_staff_can_receive_a_return_through_the_api(self):
        borrowing = self.make_borrowing()
        return_request = ReturnRequest.objects.create(
            borrowing=borrowing, user=self.student, return_method='dropoff', status='approved',
        )

        self.login_admin()
        response = self.client.post(
            f'/api/v1/library/return-requests/{return_request.pk}/receive/',
            {'condition': 'good'},
        )

        self.assertEqual(response.status_code, 200)
        borrowing.refresh_from_db()
        self.assertIsNotNone(borrowing.return_date)
