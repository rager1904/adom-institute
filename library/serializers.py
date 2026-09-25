from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Book, BookCategory, DigitalResource, BookBorrowing, BookReservation,
    DigitalResourceAccess, CourseResource, LibrarySettings, LibraryReport
)

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class BookCategorySerializer(serializers.ModelSerializer):
    """Serializer for BookCategory model"""
    total_books = serializers.ReadOnlyField()
    
    class Meta:
        model = BookCategory
        fields = [
            'id', 'name', 'description', 'color', 'is_active', 
            'total_books', 'created_at', 'updated_at'
        ]

class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model"""
    category = BookCategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    current_borrower = serializers.SerializerMethodField()
    total_borrowings = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()
    
    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'isbn', 'category', 'category_id',
            'edition', 'publisher', 'publication_year', 'pages', 'description',
            'cover_image', 'barcode', 'qr_code', 'location', 'availability',
            'condition', 'price', 'is_active', 'current_borrower',
            'total_borrowings', 'is_available', 'created_at', 'updated_at'
        ]
        read_only_fields = ['barcode', 'qr_code', 'created_at', 'updated_at']
    
    def get_current_borrower(self, obj):
        borrower = obj.current_borrower
        if borrower:
            return {
                'id': borrower.id,
                'borrower': UserSerializer(borrower.borrower).data,
                'borrowed_date': borrower.borrowed_date,
                'due_date': borrower.due_date
            }
        return None

class DigitalResourceSerializer(serializers.ModelSerializer):
    """Serializer for DigitalResource model"""
    uploaded_by = UserSerializer(read_only=True)
    file_size_mb = serializers.ReadOnlyField()
    download_available = serializers.ReadOnlyField()
    
    class Meta:
        model = DigitalResource
        fields = [
            'id', 'title', 'description', 'resource_type', 'file',
            'file_size', 'file_size_mb', 'author', 'subject', 'grade_level',
            'tags', 'access_level', 'is_downloadable', 'download_limit',
            'current_downloads', 'download_available', 'uploaded_by',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['file_size', 'current_downloads', 'uploaded_by', 'created_at', 'updated_at']

class BookBorrowingSerializer(serializers.ModelSerializer):
    """Serializer for BookBorrowing model"""
    book = BookSerializer(read_only=True)
    book_id = serializers.IntegerField(write_only=True)
    borrower = UserSerializer(read_only=True)
    borrower_id = serializers.IntegerField(write_only=True)
    returned_by = UserSerializer(read_only=True)
    is_overdue = serializers.ReadOnlyField()
    days_overdue = serializers.ReadOnlyField()
    calculated_late_fee = serializers.ReadOnlyField()
    
    class Meta:
        model = BookBorrowing
        fields = [
            'id', 'book', 'book_id', 'borrower', 'borrower_id',
            'borrowed_date', 'due_date', 'return_date', 'returned_by',
            'late_fee', 'notes', 'is_active', 'is_overdue',
            'days_overdue', 'calculated_late_fee'
        ]
        read_only_fields = ['borrowed_date', 'return_date', 'returned_by', 'late_fee']

class BookReservationSerializer(serializers.ModelSerializer):
    """Serializer for BookReservation model"""
    book = BookSerializer(read_only=True)
    book_id = serializers.IntegerField(write_only=True)
    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)
    is_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = BookReservation
        fields = [
            'id', 'book', 'book_id', 'user', 'user_id',
            'reservation_date', 'expiry_date', 'status', 'notes', 'is_expired'
        ]
        read_only_fields = ['reservation_date', 'expiry_date']

class DigitalResourceAccessSerializer(serializers.ModelSerializer):
    """Serializer for DigitalResourceAccess model"""
    resource = DigitalResourceSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DigitalResourceAccess
        fields = [
            'id', 'resource', 'user', 'access_date', 'action',
            'ip_address', 'user_agent'
        ]
        read_only_fields = ['access_date']

class CourseResourceSerializer(serializers.ModelSerializer):
    """Serializer for CourseResource model"""
    resource = DigitalResourceSerializer(read_only=True)
    recommended_by = UserSerializer(read_only=True)
    
    class Meta:
        model = CourseResource
        fields = [
            'id', 'resource', 'subject', 'grade_level', 'recommended_by',
            'is_required', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at']

class LibrarySettingsSerializer(serializers.ModelSerializer):
    """Serializer for LibrarySettings model"""
    class Meta:
        model = LibrarySettings
        fields = [
            'id', 'max_books_per_user', 'borrowing_duration_days',
            'late_fee_per_day', 'reservation_duration_hours',
            'max_reservations_per_user', 'enable_barcode', 'enable_qr_code',
            'enable_digital_resources', 'enable_reservations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class LibraryReportSerializer(serializers.ModelSerializer):
    """Serializer for LibraryReport model"""
    class Meta:
        model = LibraryReport
        fields = [
            'id', 'report_type', 'report_date', 'total_books',
            'total_borrowings', 'total_returns', 'total_overdue',
            'total_late_fees', 'total_digital_access',
            'total_digital_downloads', 'most_borrowed_books',
            'most_accessed_resources', 'created_at'
        ]
        read_only_fields = ['created_at']

# Nested serializers for detailed views
class BookDetailSerializer(BookSerializer):
    """Detailed serializer for Book with related data"""
    borrowings = BookBorrowingSerializer(many=True, read_only=True)
    reservations = BookReservationSerializer(many=True, read_only=True)
    
    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ['borrowings', 'reservations']

class DigitalResourceDetailSerializer(DigitalResourceSerializer):
    """Detailed serializer for DigitalResource with related data"""
    access_logs = DigitalResourceAccessSerializer(many=True, read_only=True)
    course_links = CourseResourceSerializer(many=True, read_only=True)
    
    class Meta(DigitalResourceSerializer.Meta):
        fields = DigitalResourceSerializer.Meta.fields + ['access_logs', 'course_links']

# Statistics serializers
class LibraryStatisticsSerializer(serializers.Serializer):
    """Serializer for library statistics"""
    total_books = serializers.IntegerField()
    available_books = serializers.IntegerField()
    borrowed_books = serializers.IntegerField()
    overdue_books = serializers.IntegerField()
    total_digital_resources = serializers.IntegerField()
    total_borrowings_today = serializers.IntegerField()
    total_returns_today = serializers.IntegerField()
    total_digital_access_today = serializers.IntegerField()
    most_borrowed_books = serializers.ListField()
    most_accessed_resources = serializers.ListField()

class UserLibraryActivitySerializer(serializers.Serializer):
    """Serializer for user library activity"""
    user = UserSerializer()
    current_borrowings = serializers.IntegerField()
    overdue_books = serializers.IntegerField()
    total_late_fees = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_reservations = serializers.IntegerField()
    total_digital_downloads = serializers.IntegerField()
    recent_activity = serializers.ListField()

# Search serializers
class BookSearchSerializer(serializers.Serializer):
    """Serializer for book search results"""
    books = BookSerializer(many=True)
    total_count = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()

class DigitalResourceSearchSerializer(serializers.Serializer):
    """Serializer for digital resource search results"""
    resources = DigitalResourceSerializer(many=True)
    total_count = serializers.IntegerField()
    page = serializers.IntegerField()
    total_pages = serializers.IntegerField()

# Action serializers
class BookBorrowActionSerializer(serializers.Serializer):
    """Serializer for book borrowing action"""
    book_id = serializers.IntegerField()
    borrower_id = serializers.IntegerField()
    due_date = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True)

class BookReturnActionSerializer(serializers.Serializer):
    """Serializer for book return action"""
    borrowing_id = serializers.IntegerField()
    return_notes = serializers.CharField(required=False, allow_blank=True)

class BookReserveActionSerializer(serializers.Serializer):
    """Serializer for book reservation action"""
    book_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)

class DigitalResourceDownloadSerializer(serializers.Serializer):
    """Serializer for digital resource download"""
    resource_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['view', 'download', 'stream'])
