from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid
import os
from accounts.validators import image_upload_validators, resource_upload_validators
from adom.protected_media import material_downloads_allowed

User = get_user_model()

def book_cover_path(instance, filename):
    """Generate file path for book covers"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('library/covers', filename)

def digital_resource_path(instance, filename):
    """Generate file path for digital resources"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('library/digital', filename)

class BookCategory(models.Model):
    """Book categories for organization"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#007bff", help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Book Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_books(self):
        return self.books.count()

class Book(models.Model):
    """Physical books in the library"""
    AVAILABILITY_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost'),
    ]

    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ]

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, unique=True, blank=True, null=True)
    category = models.ForeignKey(BookCategory, on_delete=models.CASCADE, related_name='books')
    edition = models.CharField(max_length=50, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    publication_year = models.PositiveIntegerField(blank=True, null=True)
    pages = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to=book_cover_path,
        blank=True,
        null=True,
        validators=image_upload_validators,
    )
    barcode = models.CharField(max_length=50, unique=True, blank=True, null=True)
    qr_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, help_text="Shelf location")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__isnull=True) | models.Q(price__gte=0),
                name='lib_book_price_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['availability', 'is_active'], name='lib_book_avail_idx'),
            models.Index(fields=['category', 'is_active'], name='lib_book_category_idx'),
        ]

    def __str__(self):
        return f"{self.title} by {self.author}"

    @property
    def is_available(self):
        return self.availability == 'available'

    @property
    def current_borrower(self):
        """Get current borrower if book is borrowed"""
        if self.availability == 'borrowed':
            return self.borrowings.filter(return_date__isnull=True).first()
        return None

    @property
    def total_borrowings(self):
        return self.borrowings.count()

    def generate_barcode(self):
        """Generate unique barcode if not exists"""
        if not self.barcode:
            self.barcode = f"BK{uuid.uuid4().hex[:8].upper()}"
            self.save()

    def generate_qr_code(self):
        """Generate unique QR code if not exists"""
        if not self.qr_code:
            self.qr_code = f"QR{uuid.uuid4().hex[:8].upper()}"
            self.save()

class DigitalResource(models.Model):
    """Digital resources (e-books, PDFs, videos, etc.)"""
    RESOURCE_TYPE_CHOICES = [
        ('ebook', 'E-Book'),
        ('pdf', 'PDF Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('presentation', 'Presentation'),
        ('worksheet', 'Worksheet'),
        ('other', 'Other'),
    ]

    ACCESS_LEVEL_CHOICES = [
        ('public', 'Public'),
        ('students', 'Students Only'),
        ('teachers', 'Teachers Only'),
        ('restricted', 'Restricted'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES)
    file = models.FileField(
        upload_to=digital_resource_path,
        validators=resource_upload_validators,
    )
    file_size = models.PositiveIntegerField(blank=True, null=True, help_text="File size in bytes")
    author = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=100, blank=True)
    grade_level = models.CharField(max_length=50, blank=True)
    tags = models.JSONField(default=list, blank=True)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='students')
    is_downloadable = models.BooleanField(default=True)
    download_limit = models.PositiveIntegerField(blank=True, null=True, help_text="Maximum downloads allowed")
    current_downloads = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_resources')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(current_downloads__lte=models.F('download_limit')) | models.Q(download_limit__isnull=True),
                name='lib_resource_dl_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['access_level', 'is_active'], name='lib_resource_access_idx'),
            models.Index(fields=['resource_type', 'is_active'], name='lib_resource_type_idx'),
        ]

    def __str__(self):
        return self.title

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0

    @property
    def file_view_url(self):
        """Authenticated, inline-only viewer URL for the stored file.

        Never expose ``file.url``: material must not be reachable through the
        public /media/ route.
        """
        if not self.file:
            return ''
        from django.urls import reverse
        return reverse('library:resource_file', kwargs={'resource_id': self.pk})

    @property
    def download_available(self):
        """Check if downloads are still available"""
        if not material_downloads_allowed():
            return False
        if not self.is_downloadable:
            return False
        if self.download_limit and self.current_downloads >= self.download_limit:
            return False
        return True

    def increment_download_count(self):
        """Increment download count"""
        self.current_downloads += 1
        self.save()

FULFILLMENT_METHOD_CHOICES = [
    ('pickup', 'Collect from the School Library'),
    ('delivery', 'Delivered to Me by the School'),
]


class BookBorrowing(models.Model):
    """Track book borrowing and returns"""
    FULFILLMENT_METHOD_CHOICES = FULFILLMENT_METHOD_CHOICES

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrowings')
    borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_borrowings')
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    return_date = models.DateTimeField(blank=True, null=True)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='returned_books')
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fulfillment_method = models.CharField(
        max_length=20, choices=FULFILLMENT_METHOD_CHOICES, default='pickup',
        help_text="How the book reached the borrower",
    )
    delivery_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-borrowed_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(return_date__isnull=True) | models.Q(return_date__gte=models.F('borrowed_date')),
                name='lib_borrow_return_ck',
            ),
            models.CheckConstraint(
                check=models.Q(due_date__gte=models.F('borrowed_date')),
                name='lib_borrow_due_ck',
            ),
            models.CheckConstraint(
                check=models.Q(late_fee__gte=0),
                name='lib_borrow_fee_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['borrower', 'return_date', 'due_date'], name='lib_borrow_user_idx'),
            models.Index(fields=['book', 'return_date'], name='lib_borrow_book_idx'),
        ]

    def __str__(self):
        return f"{self.book.title} - {self.borrower.get_full_name()}"

    @property
    def is_overdue(self):
        """Check if book is overdue"""
        if self.return_date:
            return False
        return timezone.now() > self.due_date

    @property
    def days_until_due(self):
        """Whole days until the due date. Negative once overdue."""
        if self.return_date:
            return 0
        return (self.due_date - timezone.now()).days

    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if self.return_date:
            if self.return_date > self.due_date:
                return (self.return_date - self.due_date).days
            return 0
        if self.is_overdue:
            return (timezone.now() - self.due_date).days
        return 0

    @property
    def calculated_late_fee(self):
        """Calculate late fee based on days overdue"""
        days = self.days_overdue
        if days > 0:
            return days * 0.50  # $0.50 per day
        return 0

    def calculate_late_fee(self):
        """Calculate and update late fee"""
        self.late_fee = self.calculated_late_fee
        self.save()

    def return_book(self, returned_by=None):
        """Mark book as returned"""
        self.return_date = timezone.now()
        self.returned_by = returned_by
        self.calculate_late_fee()
        self.book.availability = 'available'
        self.book.save()
        self.save()

class BookReservation(models.Model):
    """Student book request: request -> staff approval -> handover.

    A reservation is the student's *request* for a book. It becomes a real
    ``BookBorrowing`` only once staff hand the book over (``fulfill``), which
    is why ``borrowed_date`` is never set here.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved - Awaiting Handover'),
        ('available', 'Ready for Pickup / Dispatched'),
        ('fulfilled', 'Handed Over'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    FULFILLMENT_METHOD_CHOICES = FULFILLMENT_METHOD_CHOICES

    OPEN_STATUSES = ('pending', 'approved', 'available')

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_reservations')
    reservation_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # How the student wants to receive the book. Staff may override this on
    # approval, which is recorded in ``method_overridden``.
    fulfillment_method = models.CharField(
        max_length=20, choices=FULFILLMENT_METHOD_CHOICES, default='pickup',
    )
    delivery_address = models.TextField(blank=True)
    delivery_phone = models.CharField(max_length=40, blank=True)

    notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_book_reservations',
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    method_overridden = models.BooleanField(default=False)

    fulfilled_at = models.DateTimeField(blank=True, null=True)
    fulfilled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fulfilled_book_reservations',
    )
    borrowing = models.OneToOneField(
        BookBorrowing, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reservation',
    )

    class Meta:
        ordering = ['-reservation_date']
        constraints = [
            models.CheckConstraint(
                check=models.Q(expiry_date__gte=models.F('reservation_date')),
                name='lib_reserve_expiry_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'status'], name='lib_reserve_user_idx'),
            models.Index(fields=['book', 'status'], name='lib_reserve_book_idx'),
        ]

    def __str__(self):
        return f"{self.book.title} - {self.user.get_full_name()}"

    @property
    def is_open(self):
        """Whether this request is still live (pending, approved or ready)."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_expired(self):
        """Check if reservation is expired"""
        if self.status in ('fulfilled', 'rejected', 'cancelled'):
            return False
        return timezone.now() > self.expiry_date

    @property
    def requires_delivery(self):
        return self.fulfillment_method == 'delivery'

    def _restore_book_availability(self):
        """Free the book again unless another live request holds it."""
        if self.book.availability != 'reserved':
            return
        if self.book.reservations.filter(status__in=self.OPEN_STATUSES).exclude(pk=self.pk).exists():
            return
        if self.book.borrowings.filter(return_date__isnull=True).exists():
            self.book.availability = 'borrowed'
        else:
            self.book.availability = 'available'
        self.book.save(update_fields=['availability'])

    def approve(self, reviewed_by=None, fulfillment_method=None):
        """Approve the request, optionally overriding the fulfilment method."""
        self.status = 'approved'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        if fulfillment_method and fulfillment_method != self.fulfillment_method:
            self.fulfillment_method = fulfillment_method
            self.method_overridden = True
        if self.book.availability == 'available':
            self.book.availability = 'reserved'
            self.book.save(update_fields=['availability'])
        self.save()
        return self

    def reject(self, reviewed_by=None, staff_notes=''):
        """Decline the request."""
        self.status = 'rejected'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.staff_notes = staff_notes
        self.save()
        self._restore_book_availability()
        return self

    def mark_available(self):
        """Mark reservation as ready - shelf copy staged or courier dispatched."""
        self.status = 'available'
        self.save()
        return self

    def mark_expired(self):
        """Give up on a request whose pickup window has lapsed."""
        if not self.is_open:
            return self
        self.status = 'expired'
        self.save()
        self._restore_book_availability()
        return self

    def cancel_reservation(self):
        """Cancel the reservation"""
        if not self.is_open:
            return self
        self.status = 'cancelled'
        self.save()
        self._restore_book_availability()
        return self

    def fulfil(self, fulfilled_by=None):
        """Hand the book over, creating the real loan.

        Returns the created ``BookBorrowing``, or ``None`` when the request is
        not in a hand-over-able state.
        """
        if self.status not in ('approved', 'available'):
            return None
        if self.book.availability not in ('available', 'reserved'):
            return None

        settings = LibrarySettings.get_settings()
        borrowing = BookBorrowing.objects.create(
            book=self.book,
            borrower=self.user,
            due_date=timezone.now() + timedelta(days=settings.borrowing_duration_days),
            fulfillment_method=self.fulfillment_method,
            delivery_address=self.delivery_address,
            notes=f"Request #{self.pk} - {self.get_fulfillment_method_display()}",
        )
        self.book.availability = 'borrowed'
        self.book.save(update_fields=['availability'])

        self.status = 'fulfilled'
        self.borrowing = borrowing
        self.fulfilled_at = timezone.now()
        self.fulfilled_by = fulfilled_by
        self.save()
        return borrowing


class ReturnRequest(models.Model):
    """Student-initiated return of a borrowed book.

    A student asks to hand a book back and states how: they drop it off at the
    school library, or the school courier collects it from them. Staff approve,
    then record receipt, which closes the underlying ``BookBorrowing``.
    """
    RETURN_METHOD_CHOICES = [
        ('dropoff', 'Drop Off at the School Library'),
        ('collection', 'Collected by the School Courier'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved - Awaiting Book'),
        ('in_transit', 'In Transit'),
        ('received', 'Received at Library'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    OPEN_STATUSES = ('pending', 'approved', 'in_transit')

    borrowing = models.ForeignKey(
        BookBorrowing, on_delete=models.CASCADE, related_name='return_requests',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='book_return_requests',
    )
    return_method = models.CharField(max_length=20, choices=RETURN_METHOD_CHOICES)
    delivery_address = models.TextField(
        blank=True, help_text="Where the courier should collect the book",
    )
    delivery_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_book_return_requests',
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    method_overridden = models.BooleanField(default=False)

    received_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_book_return_requests',
    )
    received_at = models.DateTimeField(blank=True, null=True)
    condition_on_receipt = models.CharField(
        max_length=20, blank=True, choices=Book.CONDITION_CHOICES,
    )

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='lib_return_user_idx'),
            models.Index(fields=['status', 'requested_at'], name='lib_return_status_idx'),
        ]

    def __str__(self):
        return f"Return: {self.book.title} - {self.user.get_full_name()}"

    @property
    def book(self):
        return self.borrowing.book

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def requires_collection(self):
        """True when the school has to travel to the student."""
        return self.return_method == 'collection'

    def cancel(self):
        if not self.is_open:
            return self
        self.status = 'cancelled'
        self.save()
        return self

    def approve(self, reviewed_by=None, return_method=None):
        self.status = 'approved'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        if return_method and return_method != self.return_method:
            self.return_method = return_method
            self.method_overridden = True
        self.save()
        return self

    def reject(self, reviewed_by=None, staff_notes=''):
        self.status = 'rejected'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.staff_notes = staff_notes
        self.save()
        return self

    def mark_in_transit(self):
        if self.status != 'approved':
            return self
        self.status = 'in_transit'
        self.save()
        return self

    def receive(self, received_by=None, condition='', notes=''):
        """Record the book as back in the library and close the loan."""
        if self.status not in ('approved', 'in_transit'):
            return None
        self.status = 'received'
        self.received_by = received_by
        self.received_at = timezone.now()
        self.condition_on_receipt = condition or ''
        if notes:
            self.staff_notes = f"{self.staff_notes}\n{notes}".strip()
        self.save()

        self.borrowing.return_book(received_by)
        if condition:
            self.borrowing.book.condition = condition
            self.borrowing.book.save(update_fields=['condition'])
        return self.borrowing


class DigitalResourceAccess(models.Model):
    """Track digital resource access and downloads"""
    resource = models.ForeignKey(DigitalResource, on_delete=models.CASCADE, related_name='access_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resource_access')
    access_date = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, choices=[
        ('view', 'Viewed'),
        ('download', 'Downloaded'),
        ('stream', 'Streamed'),
    ])
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-access_date']
        indexes = [
            models.Index(fields=['resource', 'action', 'access_date'], name='lib_access_resource_idx'),
            models.Index(fields=['user', 'access_date'], name='lib_access_user_idx'),
        ]

    def __str__(self):
        return f"{self.resource.title} - {self.user.get_full_name()} - {self.action}"

class CourseResource(models.Model):
    """Link digital resources to courses/subjects"""
    resource = models.ForeignKey(DigitalResource, on_delete=models.CASCADE, related_name='course_links')
    subject = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=50)
    recommended_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recommended_resources')
    is_required = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subject', 'grade_level']

    def __str__(self):
        return f"{self.resource.title} - {self.subject} ({self.grade_level})"

class LibrarySettings(models.Model):
    """Library system settings"""
    max_books_per_user = models.PositiveIntegerField(default=5)
    borrowing_duration_days = models.PositiveIntegerField(default=14)
    late_fee_per_day = models.DecimalField(max_digits=5, decimal_places=2, default=0.50)
    reservation_duration_hours = models.PositiveIntegerField(default=48)
    max_reservations_per_user = models.PositiveIntegerField(default=3)
    require_approval = models.BooleanField(
        default=True,
        help_text="Staff must approve borrowing requests before a book is handed over",
    )
    enable_delivery = models.BooleanField(
        default=True,
        help_text="Allow students to have books delivered instead of collecting them",
    )
    enable_barcode = models.BooleanField(default=True)
    enable_qr_code = models.BooleanField(default=True)
    enable_digital_resources = models.BooleanField(default=True)
    enable_reservations = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Library Settings"

    def __str__(self):
        return "Library Settings"

    @classmethod
    def get_settings(cls):
        """Get or create library settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

class LibraryReport(models.Model):
    """Library usage reports and analytics"""
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    report_date = models.DateField()
    total_books = models.PositiveIntegerField(default=0)
    total_borrowings = models.PositiveIntegerField(default=0)
    total_returns = models.PositiveIntegerField(default=0)
    total_overdue = models.PositiveIntegerField(default=0)
    total_late_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_digital_access = models.PositiveIntegerField(default=0)
    total_digital_downloads = models.PositiveIntegerField(default=0)
    most_borrowed_books = models.JSONField(default=list)
    most_accessed_resources = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-report_date']
        unique_together = ['report_type', 'report_date']
        indexes = [
            models.Index(fields=['report_type', 'report_date'], name='lib_report_type_idx'),
        ]

    def __str__(self):
        return f"{self.report_type.title()} Report - {self.report_date}"

    @classmethod
    def generate_daily_report(cls, date=None):
        """Generate daily library report"""
        if not date:
            date = timezone.now().date()
        
        # Get daily statistics
        start_date = date
        end_date = date + timedelta(days=1)
        
        total_borrowings = BookBorrowing.objects.filter(
            borrowed_date__date=date
        ).count()
        
        total_returns = BookBorrowing.objects.filter(
            return_date__date=date
        ).count()
        
        total_overdue = BookBorrowing.objects.filter(
            due_date__lt=end_date,
            return_date__isnull=True
        ).count()
        
        total_late_fees = sum(
            borrowing.late_fee for borrowing in BookBorrowing.objects.filter(
                return_date__date=date
            )
        )
        
        total_digital_access = DigitalResourceAccess.objects.filter(
            access_date__date=date
        ).count()
        
        total_digital_downloads = DigitalResourceAccess.objects.filter(
            access_date__date=date,
            action='download'
        ).count()
        
        # Most borrowed books (last 30 days)
        thirty_days_ago = date - timedelta(days=30)
        most_borrowed = BookBorrowing.objects.filter(
            borrowed_date__gte=thirty_days_ago
        ).values('book__title').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        # Most accessed digital resources (last 30 days)
        most_accessed = DigitalResourceAccess.objects.filter(
            access_date__gte=thirty_days_ago
        ).values('resource__title').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        report, created = cls.objects.update_or_create(
            report_type='daily',
            report_date=date,
            defaults={
                'total_books': Book.objects.filter(is_active=True).count(),
                'total_borrowings': total_borrowings,
                'total_returns': total_returns,
                'total_overdue': total_overdue,
                'total_late_fees': total_late_fees,
                'total_digital_access': total_digital_access,
                'total_digital_downloads': total_digital_downloads,
                'most_borrowed_books': list(most_borrowed),
                'most_accessed_resources': list(most_accessed),
            }
        )
        
        return report
