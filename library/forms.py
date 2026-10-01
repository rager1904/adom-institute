from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from accounts.validators import (
    validate_learning_resource_extension,
    validate_resource_size,
    validate_safe_filename,
)
from .models import (
    Book, BookCategory, DigitalResource, BookBorrowing, BookReservation,
    CourseResource, LibrarySettings, ReturnRequest
)

User = get_user_model()

class BookSearchForm(forms.Form):
    """Search form for books"""
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, author, ISBN...'
        })
    )
    category_filter = forms.ModelChoiceField(
        queryset=BookCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    availability_filter = forms.ChoiceField(
        choices=[('', 'All')] + Book.AVAILABILITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    condition_filter = forms.ChoiceField(
        choices=[('', 'All')] + Book.CONDITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class BookForm(forms.ModelForm):
    """Form for creating/editing books"""
    class Meta:
        model = Book
        fields = [
            'title', 'author', 'isbn', 'category', 'edition', 'publisher',
            'publication_year', 'pages', 'description', 'cover_image',
            'location', 'availability', 'condition', 'price', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'edition': forms.TextInput(attrs={'class': 'form-control'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control'}),
            'publication_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'pages': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'availability': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_isbn(self):
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            # Check if ISBN already exists (excluding current instance)
            existing = Book.objects.filter(isbn=isbn)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("A book with this ISBN already exists.")
        return isbn

class BookCategoryForm(forms.ModelForm):
    """Form for creating/editing book categories"""
    class Meta:
        model = BookCategory
        fields = ['name', 'description', 'color', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class DigitalResourceSearchForm(forms.Form):
    """Search form for digital resources"""
    search = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title, author, subject...'
        })
    )
    resource_type_filter = forms.ChoiceField(
        choices=[('', 'All Types')] + DigitalResource.RESOURCE_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    access_level_filter = forms.ChoiceField(
        choices=[('', 'All Levels')] + DigitalResource.ACCESS_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    subject_filter = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by subject...'
        })
    )
    grade_level_filter = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by grade...'
        })
    )

class DigitalResourceForm(forms.ModelForm):
    """Form for creating/editing digital resources"""
    class Meta:
        model = DigitalResource
        fields = [
            'title', 'description', 'resource_type', 'file', 'author',
            'subject', 'grade_level', 'tags', 'access_level',
            'is_downloadable', 'download_limit', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'resource_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'grade_level': forms.TextInput(attrs={'class': 'form-control'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tags separated by commas'
            }),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'is_downloadable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'download_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if tags:
            # Convert comma-separated string to list
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            return tag_list
        return []

class BookBorrowingForm(forms.ModelForm):
    """Form for creating book borrowings"""
    class Meta:
        model = BookBorrowing
        fields = ['book', 'borrower', 'due_date', 'notes']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select'}),
            'borrower': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show available books
        self.fields['book'].queryset = Book.objects.filter(
            availability='available',
            is_active=True
        )
        # Only show active users
        self.fields['borrower'].queryset = User.objects.filter(is_active=True)

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date <= timezone.now():
            raise forms.ValidationError("Due date must be in the future.")
        return due_date

    def clean(self):
        cleaned_data = super().clean()
        borrower = cleaned_data.get('borrower')
        book = cleaned_data.get('book')
        
        if borrower and book:
            # Check if user has reached borrowing limit
            settings = LibrarySettings.get_settings()
            current_borrowings = BookBorrowing.objects.filter(
                borrower=borrower,
                return_date__isnull=True
            ).count()
            
            if current_borrowings >= settings.max_books_per_user:
                raise forms.ValidationError(
                    f"User has reached the maximum borrowing limit of {settings.max_books_per_user} books."
                )
            
            # Check if book is available
            if book.availability != 'available':
                raise forms.ValidationError("This book is not available for borrowing.")
        
        return cleaned_data

class BookReturnForm(forms.Form):
    """Form for returning books"""
    return_notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes about the return...'
        })
    )

class BookReservationForm(forms.ModelForm):
    """Form for creating book reservations on behalf of a member"""
    class Meta:
        model = BookReservation
        fields = ['book', 'user', 'fulfillment_method', 'delivery_address', 'delivery_phone', 'notes']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select'}),
            'user': forms.Select(attrs={'class': 'form-select'}),
            'fulfillment_method': forms.Select(attrs={'class': 'form-select'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'delivery_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show unavailable books
        self.fields['book'].queryset = Book.objects.filter(
            availability__in=['borrowed', 'reserved'],
            is_active=True
        )
        # Only show active users
        self.fields['user'].queryset = User.objects.filter(is_active=True)
        if not LibrarySettings.get_settings().enable_delivery:
            self.fields['fulfillment_method'].choices = [
                (value, label) for value, label in BookReservation.FULFILLMENT_METHOD_CHOICES
                if value == 'pickup'
            ]
            self.fields['fulfillment_method'].initial = 'pickup'
            self.fields['fulfillment_method'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        book = cleaned_data.get('book')
        
        if user and book:
            # Check if user has reached reservation limit
            settings = LibrarySettings.get_settings()
            current_reservations = BookReservation.objects.filter(
                user=user,
                status='pending'
            ).count()
            
            if current_reservations >= settings.max_reservations_per_user:
                raise forms.ValidationError(
                    f"User has reached the maximum reservation limit of {settings.max_reservations_per_user} books."
                )
            
            # Check if user already has a reservation for this book
            existing_reservation = BookReservation.objects.filter(
                user=user,
                book=book,
                status='pending'
            ).exists()
            
            if existing_reservation:
                raise forms.ValidationError("User already has a pending reservation for this book.")
        
        return cleaned_data


class BookRequestForm(forms.ModelForm):
    """Student-facing book request.

    The student picks how they want the book: collected from the school
    library, or delivered to them by the school. Staff review it before the
    book changes hands.
    """

    class Meta:
        model = BookReservation
        fields = ['book', 'fulfillment_method', 'delivery_address', 'delivery_phone', 'notes']
        widgets = {
            'book': forms.Select(attrs={'class': 'form-select'}),
            'fulfillment_method': forms.RadioSelect(),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Where should the school deliver the book?',
            }),
            'delivery_phone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Contact number for the courier',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Anything the library should know? (optional)',
            }),
        }
        labels = {
            'fulfillment_method': 'How would you like to receive this book?',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['book'].queryset = Book.objects.filter(
            availability__in=['available', 'borrowed', 'reserved'],
            is_active=True,
        )
        self.fields['book'].empty_label = "Choose a book"
        self.fields['fulfillment_method'].initial = 'pickup'

        settings = LibrarySettings.get_settings()
        if not settings.enable_delivery:
            self.fields['fulfillment_method'].choices = [
                (value, label) for value, label in BookReservation.FULFILLMENT_METHOD_CHOICES
                if value == 'pickup'
            ]
            self.fields['fulfillment_method'].initial = 'pickup'
            self.fields['fulfillment_method'].widget = forms.HiddenInput()

    def clean_book(self):
        book = self.cleaned_data['book']
        if self.user and BookReservation.objects.filter(
            user=self.user,
            book=book,
            status__in=BookReservation.OPEN_STATUSES,
        ).exists():
            raise forms.ValidationError(
                "You already have a live request for this book."
            )
        return book

    def clean(self):
        cleaned_data = super().clean()
        settings = LibrarySettings.get_settings()

        if not settings.enable_reservations:
            raise forms.ValidationError("Book requests are currently disabled.")

        if self.user:
            open_requests = BookReservation.objects.filter(
                user=self.user,
                status__in=BookReservation.OPEN_STATUSES,
            ).count()
            if open_requests >= settings.max_reservations_per_user:
                raise forms.ValidationError(
                    f"You already have {open_requests} open requests, which is the "
                    f"maximum of {settings.max_reservations_per_user}."
                )

        if cleaned_data.get('fulfillment_method') == 'delivery':
            if not settings.enable_delivery:
                raise forms.ValidationError("Delivery is currently unavailable. Please choose pickup.")
            if not (cleaned_data.get('delivery_address') or '').strip():
                raise forms.ValidationError(
                    "Please give a delivery address, or choose pickup from the library."
                )

        return cleaned_data


class BookRequestDecisionForm(forms.Form):
    """Staff decision on a pending book request."""

    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        widget=forms.HiddenInput(),
    )
    fulfillment_method = forms.ChoiceField(
        choices=BookReservation.FULFILLMENT_METHOD_CHOICES,
        required=False,
        label='Fulfil with',
        help_text="Leave as-is unless you need to change how the student receives it.",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    staff_notes = forms.CharField(
        required=False,
        label='Notes',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        self.reservation = kwargs.pop('reservation', None)
        super().__init__(*args, **kwargs)
        if self.reservation is not None:
            self.fields['fulfillment_method'].initial = self.reservation.fulfillment_method

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('action') == 'reject' and not (cleaned_data.get('staff_notes') or '').strip():
            self.add_error('staff_notes', "Tell the student why the request was rejected.")
        if not LibrarySettings.get_settings().enable_delivery:
            cleaned_data['fulfillment_method'] = 'pickup'
        return cleaned_data


class BookReturnRequestForm(forms.ModelForm):
    """Student-initiated return of a book they are holding.

    The student either drops the book off at the school library, or the school
    courier collects it from them.
    """

    class Meta:
        model = ReturnRequest
        fields = ['return_method', 'delivery_address', 'delivery_phone', 'notes']
        widgets = {
            'return_method': forms.RadioSelect(),
            'delivery_address': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Where should the courier collect the book?',
            }),
            'delivery_phone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Contact number for the courier',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Anything the library should know? (optional)',
            }),
        }
        labels = {
            'return_method': 'How would you like to return this book?',
        }

    def __init__(self, *args, **kwargs):
        self.borrowing = kwargs.pop('borrowing', None)
        super().__init__(*args, **kwargs)
        self.fields['return_method'].initial = 'dropoff'

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_borrowing = self.borrowing

        if self.borrowing is None:
            raise forms.ValidationError("Select a book to return.")
        if self.borrowing.return_date is not None:
            raise forms.ValidationError("This book has already been returned.")
        if ReturnRequest.objects.filter(
            borrowing=self.borrowing,
            status__in=ReturnRequest.OPEN_STATUSES,
        ).exists():
            raise forms.ValidationError(
                "You already have an open return request for this book."
            )

        if cleaned_data.get('return_method') == 'collection':
            if not (cleaned_data.get('delivery_address') or '').strip():
                raise forms.ValidationError(
                    "Please give a collection address, or drop the book off instead."
                )
            if not (cleaned_data.get('delivery_phone') or '').strip():
                raise forms.ValidationError("A contact number is required for a courier collection.")

        return cleaned_data


class BookReturnDecisionForm(forms.Form):
    """Staff decision on a pending return request."""

    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')],
        widget=forms.HiddenInput(),
    )
    return_method = forms.ChoiceField(
        choices=ReturnRequest.RETURN_METHOD_CHOICES,
        required=False,
        label='Handle as',
        help_text="Leave as-is unless the student agreed to a different arrangement.",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    staff_notes = forms.CharField(
        required=False,
        label='Notes',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        self.return_request = kwargs.pop('return_request', None)
        super().__init__(*args, **kwargs)
        if self.return_request is not None:
            self.fields['return_method'].initial = self.return_request.return_method

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('action') == 'reject' and not (cleaned_data.get('staff_notes') or '').strip():
            self.add_error('staff_notes', "Tell the student why the return request was rejected.")
        return cleaned_data


class BookReturnReceiveForm(forms.Form):
    """Staff recording the physical receipt of a returned book."""

    condition = forms.ChoiceField(
        choices=[('', "Leave unchanged")] + Book.CONDITION_CHOICES,
        required=False,
        label='Condition on receipt',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    return_notes = forms.CharField(
        required=False,
        label='Notes',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'Optional notes about the return...',
        }),
    )


class CourseResourceForm(forms.ModelForm):
    """Form for creating/editing course resources"""
    class Meta:
        model = CourseResource
        fields = ['resource', 'subject', 'grade_level', 'is_required', 'notes']
        widgets = {
            'resource': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'grade_level': forms.TextInput(attrs={'class': 'form-control'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class LibrarySettingsForm(forms.ModelForm):
    """Form for library settings"""
    class Meta:
        model = LibrarySettings
        fields = [
            'max_books_per_user', 'borrowing_duration_days', 'late_fee_per_day',
            'reservation_duration_hours', 'max_reservations_per_user',
            'enable_barcode', 'enable_qr_code', 'enable_digital_resources',
            'enable_reservations'
        ]
        widgets = {
            'max_books_per_user': forms.NumberInput(attrs={'class': 'form-control'}),
            'borrowing_duration_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'late_fee_per_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'reservation_duration_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_reservations_per_user': forms.NumberInput(attrs={'class': 'form-control'}),
            'enable_barcode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_qr_code': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_digital_resources': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_reservations': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class BulkBookImportForm(forms.Form):
    """Form for bulk importing books"""
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        }),
        help_text="Upload a CSV file with columns: title, author, isbn, category, edition, publisher, publication_year, pages, description, location, price"
    )
    category_mapping = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter category mappings (e.g., "Fiction:Novels, Non-Fiction:Reference")'
        }),
        required=False,
        help_text="Map CSV categories to existing categories (format: csv_category:existing_category)"
    )

class BookBarcodeScanForm(forms.Form):
    """Form for barcode scanning"""
    barcode = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Scan or enter barcode...',
            'autofocus': True
        })
    )

class DigitalResourceUploadForm(forms.ModelForm):
    """Form for uploading digital resources"""
    class Meta:
        model = DigitalResource
        fields = [
            'title', 'description', 'resource_type', 'file', 'author',
            'subject', 'grade_level', 'tags', 'access_level',
            'is_downloadable', 'download_limit'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'resource_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'author': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'grade_level': forms.TextInput(attrs={'class': 'form-control'}),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter tags separated by commas'
            }),
            'access_level': forms.Select(attrs={'class': 'form-select'}),
            'is_downloadable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'download_limit': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            try:
                validate_safe_filename(file)
                validate_resource_size(file)
                validate_learning_resource_extension(file)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc
        
        return file

    def clean_tags(self):
        tags = self.cleaned_data.get('tags')
        if isinstance(tags, list):
            return tags
        if tags:
            return [tag.strip() for tag in str(tags).split(',') if tag.strip()]
        return []
