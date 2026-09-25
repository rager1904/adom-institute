from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import uuid
import os
from accounts.validators import image_upload_validators, resource_upload_validators

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
    def download_available(self):
        """Check if downloads are still available"""
        if not self.is_downloadable:
            return False
        if self.download_limit and self.current_downloads >= self.download_limit:
            return False
        return True

    def increment_download_count(self):
        """Increment download count"""
        self.current_downloads += 1
        self.save()

class BookBorrowing(models.Model):
    """Track book borrowing and returns"""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrowings')
    borrower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_borrowings')
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    return_date = models.DateTimeField(blank=True, null=True)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='returned_books')
    late_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    """Book reservation system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('available', 'Available for Pickup'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_reservations')
    reservation_date = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

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
    def is_expired(self):
        """Check if reservation is expired"""
        return timezone.now() > self.expiry_date

    def mark_available(self):
        """Mark reservation as available for pickup"""
        self.status = 'available'
        self.save()

    def cancel_reservation(self):
        """Cancel the reservation"""
        self.status = 'cancelled'
        self.save()

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
