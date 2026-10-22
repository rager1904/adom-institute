"""Library report builders.

The library report page renders its panels in the browser and expects a JSON
payload per report type.  The endpoints that served that payload were missing,
so every panel ended in "An error occurred while generating the report".

The payload shapes below mirror ``templates/library/reports.html``.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    Book, BookBorrowing, BookReservation, DigitalResource, DigitalResourceAccess,
    LibrarySettings,
)

REPORT_TYPES = (
    'borrowing_summary',
    'overdue_books',
    'popular_books',
    'user_activity',
    'inventory_status',
    'fines_revenue',
    'digital_resources',
    'reservations',
    'monthly_stats',
)

REPORT_TITLES = {
    'borrowing_summary': 'Borrowing Summary Report',
    'overdue_books': 'Overdue Books Report',
    'popular_books': 'Popular Books Report',
    'user_activity': 'User Activity Report',
    'inventory_status': 'Inventory Status Report',
    'fines_revenue': 'Fines & Revenue Report',
    'digital_resources': 'Digital Resources Report',
    'reservations': 'Reservations Report',
    'monthly_stats': 'Monthly Statistics Report',
}

DEFAULT_LATE_FEE_PER_DAY = Decimal('0.50')


def _late_fee_per_day():
    settings = LibrarySettings.objects.first()
    if settings and settings.late_fee_per_day is not None:
        return Decimal(settings.late_fee_per_day)
    return DEFAULT_LATE_FEE_PER_DAY


def _date_range(params):
    """Return the (start, end) datetimes selected by the report filters."""
    now = timezone.now()
    date_range = (params.get('date_range') or '30').strip()

    if date_range == 'custom':
        start = params.get('from_date')
        end = params.get('to_date')
        try:
            start_dt = timezone.make_aware(
                datetime.combine(datetime.strptime(start, '%Y-%m-%d').date(), time.min),
                timezone.get_current_timezone(),
            )
        except (TypeError, ValueError):
            start_dt = now - timedelta(days=30)
        try:
            end_dt = timezone.make_aware(
                datetime.combine(datetime.strptime(end, '%Y-%m-%d').date(), time.max),
                timezone.get_current_timezone(),
            )
        except (TypeError, ValueError):
            end_dt = now
        return start_dt, end_dt

    try:
        days = int(date_range)
    except (TypeError, ValueError):
        days = 30
    days = max(days, 1)
    return now - timedelta(days=days), now


def _books(params):
    queryset = Book.objects.filter(is_active=True)
    category = params.get('category')
    if category:
        queryset = queryset.filter(category_id=category)
    return queryset


def _borrowings(params):
    start, end = _date_range(params)
    return (
        BookBorrowing.objects
        .select_related('book', 'borrower')
        .filter(borrowed_date__gte=start, borrowed_date__lte=end)
    )


def borrowing_summary(params, user=None):
    borrowings = _borrowings(params)
    active = borrowings.filter(return_date__isnull=True)
    overdue = active.filter(due_date__lt=timezone.now())
    return {
        'total_borrowings': borrowings.count(),
        'active_borrowings': active.count(),
        'returned_borrowings': borrowings.filter(return_date__isnull=False).count(),
        'overdue_borrowings': overdue.count(),
    }


def overdue_books(params, user=None):
    start, end = _date_range(params)
    overdue = (
        BookBorrowing.objects
        .select_related('book', 'borrower')
        .filter(return_date__isnull=True, due_date__lt=timezone.now())
        .filter(borrowed_date__gte=start, borrowed_date__lte=end)
    )
    fee_per_day = _late_fee_per_day()
    rows = []
    for borrowing in overdue:
        days_overdue = (timezone.now().date() - borrowing.due_date.date()).days
        fine = Decimal(borrowing.late_fee or 0) + (Decimal(max(days_overdue, 0)) * fee_per_day)
        rows.append({
            'title': borrowing.book.title,
            'borrower': borrowing.borrower.get_full_name(),
            'due_date': borrowing.due_date.strftime('%Y-%m-%d'),
            'days_overdue': days_overdue,
            'fine_amount': fine,
        })
    return {'overdue_books': rows}


def popular_books(params, user=None):
    rows = list(
        _borrowings(params)
        .values('book__title', 'book__author')
        .annotate(borrow_count=Count('id'))
        .order_by('-borrow_count')[:10]
    )
    top_count = rows[0]['borrow_count'] if rows else 0
    books = []
    for row in rows:
        score = round((row['borrow_count'] / top_count) * 100) if top_count else 0
        books.append({
            'title': row['book__title'],
            'author': row['book__author'],
            'borrow_count': row['borrow_count'],
            'popularity_score': score,
        })
    return {'popular_books': books}


def user_activity(params, user=None):
    start, end = _date_range(params)
    borrowings = _borrowings(params)
    active_users = borrowings.values('borrower_id').distinct().count()
    new_users = (
        borrowings
        .filter(borrower__date_joined__gte=start, borrower__date_joined__lte=end)
        .values('borrower_id').distinct().count()
    )
    total_borrowings = borrowings.count()
    avg_books = round(total_borrowings / active_users, 2) if active_users else 0
    return {
        'active_users': active_users,
        'new_users': new_users,
        'avg_books_per_user': avg_books,
    }


def inventory_status(params, user=None):
    books = _books(params)
    return {
        'total_books': books.count(),
        'available_books': books.filter(availability='available').count(),
        'borrowed_books': books.filter(availability='borrowed').count(),
        'reserved_books': books.filter(availability='reserved').count(),
    }


def fines_revenue(params, user=None):
    borrowings = _borrowings(params)
    collected = borrowings.filter(return_date__isnull=False).aggregate(
        total=Sum('late_fee')
    )['total'] or Decimal('0')
    pending = borrowings.filter(return_date__isnull=True).aggregate(
        total=Sum('late_fee')
    )['total'] or Decimal('0')
    return {
        'total_revenue': collected + pending,
        'pending_fines': pending,
        'collected_fines': collected,
    }


def digital_resources(params, user=None):
    if user is not None:
        from .views import resources_visible_to
        resources = resources_visible_to(user).filter(is_active=True)
    else:
        resources = DigitalResource.objects.filter(is_active=True)
    resource_ids = list(resources.values_list('id', flat=True))
    accesses = DigitalResourceAccess.objects.filter(resource_id__in=resource_ids)
    total_downloads = accesses.filter(action='download').count()
    unique_users = accesses.values('user_id').distinct().count()
    resource_count = resources.count()
    return {
        'total_resources': resource_count,
        'total_downloads': total_downloads,
        'unique_users': unique_users,
        'avg_downloads': round(total_downloads / resource_count, 2) if resource_count else 0,
    }


def reservations(params, user=None):
    start, end = _date_range(params)
    reservations_qs = BookReservation.objects.filter(
        reservation_date__gte=start, reservation_date__lte=end
    )
    return {
        'total_reservations': reservations_qs.count(),
        'active_reservations': reservations_qs.filter(
            status__in=BookReservation.OPEN_STATUSES
        ).count(),
        'fulfilled_reservations': reservations_qs.filter(status='fulfilled').count(),
    }


def monthly_stats(params, user=None):
    start, end = _date_range(params)
    borrowings = _borrowings(params)
    reservations_qs = BookReservation.objects.filter(
        reservation_date__gte=start, reservation_date__lte=end
    )
    new_books = Book.objects.filter(created_at__gte=start, created_at__lte=end).count()
    fines = borrowings.aggregate(total=Sum('late_fee'))['total'] or Decimal('0')
    users = borrowings.values('borrower_id').distinct().count()
    return {
        'monthly_borrowings': borrowings.count(),
        'monthly_returns': borrowings.filter(return_date__isnull=False).count(),
        'monthly_reservations': reservations_qs.count(),
        'monthly_new_books': new_books,
        'monthly_fines': fines,
        'monthly_users': users,
    }


BUILDERS = {
    'borrowing_summary': borrowing_summary,
    'overdue_books': overdue_books,
    'popular_books': popular_books,
    'user_activity': user_activity,
    'inventory_status': inventory_status,
    'fines_revenue': fines_revenue,
    'digital_resources': digital_resources,
    'reservations': reservations,
    'monthly_stats': monthly_stats,
}


def build_report(report_type, params, user=None):
    """Return the payload for ``report_type`` or ``None`` when unknown."""
    builder = BUILDERS.get(report_type)
    if builder is None:
        return None
    return builder(params, user)


def report_rows(report_type, data):
    """Return (headers, rows) so the data can also be exported."""
    if report_type == 'overdue_books':
        return (
            ['Title', 'Borrower', 'Due date', 'Days overdue', 'Fine amount'],
            [
                [row['title'], row['borrower'], row['due_date'], row['days_overdue'], row['fine_amount']]
                for row in data['overdue_books']
            ],
        )
    if report_type == 'popular_books':
        return (
            ['Title', 'Author', 'Borrow count', 'Popularity score'],
            [
                [row['title'], row['author'], row['borrow_count'], row['popularity_score']]
                for row in data['popular_books']
            ],
        )

    headers = []
    rows = []
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            continue
        headers.append(key.replace('_', ' ').title())
        rows.append([value])
    return headers, rows
