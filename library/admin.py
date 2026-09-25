from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    BookCategory, Book, DigitalResource, BookBorrowing, BookReservation,
    DigitalResourceAccess, CourseResource, LibrarySettings, LibraryReport
)

@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'total_books', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']

    def total_books(self, obj):
        return obj.total_books
    total_books.short_description = 'Total Books'

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'category', 'isbn', 'availability', 
        'condition', 'current_borrower', 'total_borrowings'
    ]
    list_filter = [
        'category', 'availability', 'condition', 'is_active', 
        'publication_year', 'created_at'
    ]
    search_fields = ['title', 'author', 'isbn', 'barcode', 'qr_code']
    readonly_fields = [
        'created_at', 'updated_at', 'current_borrower', 
        'total_borrowings', 'cover_preview'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'author', 'isbn', 'category', 'edition', 'publisher')
        }),
        ('Details', {
            'fields': ('publication_year', 'pages', 'description', 'price')
        }),
        ('Identification', {
            'fields': ('barcode', 'qr_code', 'location')
        }),
        ('Status', {
            'fields': ('availability', 'condition', 'is_active')
        }),
        ('Media', {
            'fields': ('cover_image', 'cover_preview')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['generate_barcodes', 'generate_qr_codes', 'mark_available']

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.cover_image.url
            )
        return "No cover image"
    cover_preview.short_description = 'Cover Preview'

    def current_borrower(self, obj):
        borrower = obj.current_borrower
        if borrower:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:library_bookborrowing_change', args=[borrower.id]),
                borrower.borrower.get_full_name()
            )
        return "Available"
    current_borrower.short_description = 'Current Borrower'

    def total_borrowings(self, obj):
        return obj.total_borrowings
    total_borrowings.short_description = 'Total Borrowings'

    def generate_barcodes(self, request, queryset):
        for book in queryset:
            book.generate_barcode()
        self.message_user(request, f"Generated barcodes for {queryset.count()} books.")
    generate_barcodes.short_description = "Generate barcodes for selected books"

    def generate_qr_codes(self, request, queryset):
        for book in queryset:
            book.generate_qr_code()
        self.message_user(request, f"Generated QR codes for {queryset.count()} books.")
    generate_qr_codes.short_description = "Generate QR codes for selected books"

    def mark_available(self, request, queryset):
        updated = queryset.update(availability='available')
        self.message_user(request, f"Marked {updated} books as available.")
    mark_available.short_description = "Mark selected books as available"

@admin.register(DigitalResource)
class DigitalResourceAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'resource_type', 'author', 'subject', 'grade_level',
        'access_level', 'current_downloads', 'download_available', 'uploaded_by'
    ]
    list_filter = [
        'resource_type', 'access_level', 'is_downloadable', 'is_active',
        'created_at', 'subject', 'grade_level'
    ]
    search_fields = ['title', 'author', 'subject', 'description', 'tags']
    readonly_fields = [
        'created_at', 'updated_at', 'file_size_mb', 'current_downloads'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'resource_type', 'file')
        }),
        ('Metadata', {
            'fields': ('author', 'subject', 'grade_level', 'tags')
        }),
        ('Access Control', {
            'fields': ('access_level', 'is_downloadable', 'download_limit')
        }),
        ('Statistics', {
            'fields': ('file_size_mb', 'current_downloads')
        }),
        ('Upload Info', {
            'fields': ('uploaded_by', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['reset_download_count', 'make_public']

    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'

    def download_available(self, obj):
        if obj.download_available:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    download_available.short_description = 'Download Available'

    def reset_download_count(self, request, queryset):
        updated = queryset.update(current_downloads=0)
        self.message_user(request, f"Reset download count for {updated} resources.")
    reset_download_count.short_description = "Reset download count for selected resources"

    def make_public(self, request, queryset):
        updated = queryset.update(access_level='public')
        self.message_user(request, f"Made {updated} resources public.")
    make_public.short_description = "Make selected resources public"

@admin.register(BookBorrowing)
class BookBorrowingAdmin(admin.ModelAdmin):
    list_display = [
        'book', 'borrower', 'borrowed_date', 'due_date', 'return_date',
        'is_overdue', 'late_fee', 'status'
    ]
    list_filter = [
        'borrowed_date', 'due_date', 'return_date', 'is_active',
        ('book__category', admin.RelatedOnlyFieldListFilter)
    ]
    search_fields = [
        'book__title', 'book__author', 'borrower__first_name', 
        'borrower__last_name', 'borrower__email'
    ]
    readonly_fields = [
        'borrowed_date', 'is_overdue', 'days_overdue', 'calculated_late_fee'
    ]
    fieldsets = (
        ('Book Information', {
            'fields': ('book', 'borrower')
        }),
        ('Borrowing Details', {
            'fields': ('borrowed_date', 'due_date', 'return_date', 'returned_by')
        }),
        ('Fees & Status', {
            'fields': ('late_fee', 'calculated_late_fee', 'is_active')
        }),
        ('Additional Info', {
            'fields': ('notes',)
        }),
    )
    actions = ['calculate_late_fees', 'mark_returned']

    def is_overdue(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">Overdue</span>')
        return format_html('<span style="color: green;">On Time</span>')
    is_overdue.short_description = 'Status'

    def status(self, obj):
        if obj.return_date:
            return "Returned"
        elif obj.is_overdue:
            return "Overdue"
        else:
            return "Active"
    status.short_description = 'Borrowing Status'

    def calculate_late_fees(self, request, queryset):
        for borrowing in queryset:
            borrowing.calculate_late_fee()
        self.message_user(request, f"Calculated late fees for {queryset.count()} borrowings.")
    calculate_late_fees.short_description = "Calculate late fees for selected borrowings"

    def mark_returned(self, request, queryset):
        for borrowing in queryset:
            if not borrowing.return_date:
                borrowing.return_book(request.user)
        self.message_user(request, f"Marked {queryset.count()} books as returned.")
    mark_returned.short_description = "Mark selected books as returned"

@admin.register(BookReservation)
class BookReservationAdmin(admin.ModelAdmin):
    list_display = [
        'book', 'user', 'reservation_date', 'expiry_date', 
        'status', 'is_expired'
    ]
    list_filter = ['status', 'reservation_date', 'expiry_date']
    search_fields = [
        'book__title', 'user__first_name', 'user__last_name', 'user__email'
    ]
    readonly_fields = ['reservation_date', 'is_expired']
    actions = ['mark_available', 'cancel_reservations']

    def is_expired(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')
    is_expired.short_description = 'Expired'

    def mark_available(self, request, queryset):
        for reservation in queryset:
            reservation.mark_available()
        self.message_user(request, f"Marked {queryset.count()} reservations as available.")
    mark_available.short_description = "Mark selected reservations as available"

    def cancel_reservations(self, request, queryset):
        for reservation in queryset:
            reservation.cancel_reservation()
        self.message_user(request, f"Cancelled {queryset.count()} reservations.")
    cancel_reservations.short_description = "Cancel selected reservations"

@admin.register(DigitalResourceAccess)
class DigitalResourceAccessAdmin(admin.ModelAdmin):
    list_display = [
        'resource', 'user', 'action', 'access_date', 'ip_address'
    ]
    list_filter = ['action', 'access_date', 'resource__resource_type']
    search_fields = [
        'resource__title', 'user__first_name', 'user__last_name', 
        'user__email', 'ip_address'
    ]
    readonly_fields = ['access_date']
    date_hierarchy = 'access_date'

@admin.register(CourseResource)
class CourseResourceAdmin(admin.ModelAdmin):
    list_display = [
        'resource', 'subject', 'grade_level', 'recommended_by', 
        'is_required', 'created_at'
    ]
    list_filter = ['subject', 'grade_level', 'is_required', 'created_at']
    search_fields = [
        'resource__title', 'subject', 'grade_level', 
        'recommended_by__first_name', 'recommended_by__last_name'
    ]
    readonly_fields = ['created_at']

@admin.register(LibrarySettings)
class LibrarySettingsAdmin(admin.ModelAdmin):
    list_display = [
        'max_books_per_user', 'borrowing_duration_days', 
        'late_fee_per_day', 'enable_digital_resources'
    ]
    readonly_fields = ['created_at', 'updated_at']

    def has_add_permission(self, request):
        # Only allow one settings instance
        return not LibrarySettings.objects.exists()

@admin.register(LibraryReport)
class LibraryReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_type', 'report_date', 'total_books', 'total_borrowings',
        'total_overdue', 'total_late_fees', 'total_digital_access'
    ]
    list_filter = ['report_type', 'report_date']
    readonly_fields = [
        'report_type', 'report_date', 'total_books', 'total_borrowings',
        'total_returns', 'total_overdue', 'total_late_fees',
        'total_digital_access', 'total_digital_downloads',
        'most_borrowed_books', 'most_accessed_resources', 'created_at'
    ]
    date_hierarchy = 'report_date'
    actions = ['generate_daily_report']

    def generate_daily_report(self, request, queryset):
        from datetime import date
        report = LibraryReport.generate_daily_report(date.today())
        self.message_user(request, f"Generated daily report for {report.report_date}.")
    generate_daily_report.short_description = "Generate daily report for today"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
