from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
)
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from datetime import timedelta
import csv
import io
from adom.protected_media import material_downloads_allowed, protected_file_response
from accounts.permissions import (
    AdminRequiredMixin, AcademicStaffRequiredMixin, IsMaterialMaintainer,
    is_admin_user, is_teacher_user,
)

from .models import (
    Book, BookCategory, DigitalResource, BookBorrowing, BookReservation,
    DigitalResourceAccess, CourseResource, LibrarySettings, LibraryReport
)
from .forms import (
    BookSearchForm, BookForm, BookCategoryForm, DigitalResourceSearchForm,
    DigitalResourceForm, BookBorrowingForm, BookReturnForm, BookReservationForm,
    CourseResourceForm, LibrarySettingsForm, BulkBookImportForm,
    BookBarcodeScanForm, DigitalResourceUploadForm
)
from .serializers import (
    BookSerializer, BookCategorySerializer, DigitalResourceSerializer,
    BookBorrowingSerializer, BookReservationSerializer, DigitalResourceAccessSerializer,
    CourseResourceSerializer, LibrarySettingsSerializer, LibraryReportSerializer,
    BookDetailSerializer, DigitalResourceDetailSerializer, LibraryStatisticsSerializer,
    UserLibraryActivitySerializer, BookSearchSerializer, DigitalResourceSearchSerializer,
    BookBorrowActionSerializer, BookReturnActionSerializer, BookReserveActionSerializer,
    DigitalResourceDownloadSerializer
)

User = get_user_model()


def can_view_resource(user, resource):
    """Whether ``user`` may read the stored file of ``resource``."""
    if not user or not user.is_authenticated:
        return False
    if not resource.is_active:
        return False
    if is_admin_user(user):
        return True
    user_type = getattr(user, 'user_type', '')
    if resource.access_level == 'public':
        return True
    if resource.access_level == 'restricted':
        return is_teacher_user(user)
    if resource.access_level == 'teachers':
        return is_teacher_user(user)
    if resource.access_level == 'students':
        return user_type in ('student', 'parent', 'teacher')
    return is_teacher_user(user)


def can_manage_resources(user):
    """Only admins and teachers may upload, edit or delete material."""
    if not user or not user.is_authenticated:
        return False
    return is_admin_user(user) or is_teacher_user(user)


# API Viewsets
class BookViewSet(viewsets.ModelViewSet):
    """API viewset for Book model"""
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'availability', 'condition', 'is_active']
    search_fields = ['title', 'author', 'isbn', 'description']
    ordering_fields = ['title', 'author', 'created_at', 'total_borrowings']
    ordering = ['title']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BookDetailSerializer
        return BookSerializer

    @action(detail=True, methods=['post'])
    def borrow(self, request, pk=None):
        """Borrow a book"""
        book = self.get_object()
        serializer = BookBorrowActionSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                borrower = User.objects.get(id=serializer.validated_data['borrower_id'])
                due_date = serializer.validated_data['due_date']
                notes = serializer.validated_data.get('notes', '')
                
                borrowing = BookBorrowing.objects.create(
                    book=book,
                    borrower=borrower,
                    due_date=due_date,
                    notes=notes
                )
                
                book.availability = 'borrowed'
                book.save()
                
                return Response({
                    'message': 'Book borrowed successfully',
                    'borrowing_id': borrowing.id
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reserve(self, request, pk=None):
        """Reserve a book"""
        book = self.get_object()
        serializer = BookReserveActionSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = User.objects.get(id=serializer.validated_data['user_id'])
                notes = serializer.validated_data.get('notes', '')
                
                settings = LibrarySettings.get_settings()
                expiry_date = timezone.now() + timedelta(hours=settings.reservation_duration_hours)
                
                reservation = BookReservation.objects.create(
                    book=book,
                    user=user,
                    expiry_date=expiry_date,
                    notes=notes
                )
                
                return Response({
                    'message': 'Book reserved successfully',
                    'reservation_id': reservation.id
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookCategoryViewSet(viewsets.ModelViewSet):
    """API viewset for BookCategory model"""
    queryset = BookCategory.objects.all()
    serializer_class = BookCategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']

class DigitalResourceViewSet(viewsets.ModelViewSet):
    """API viewset for DigitalResource model.

    Reads are open to any authenticated user; writes are limited to admins and
    teachers. The raw file URL is never exposed - clients get the inline
    viewer URL instead.
    """
    queryset = DigitalResource.objects.all()
    serializer_class = DigitalResourceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['resource_type', 'access_level', 'is_active', 'subject', 'grade_level']
    search_fields = ['title', 'author', 'description', 'tags']
    ordering_fields = ['title', 'created_at', 'current_downloads']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsMaterialMaintainer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and not is_admin_user(self.request.user):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DigitalResourceDetailSerializer
        return DigitalResourceSerializer

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['get'])
    def file(self, request, pk=None):
        """Stream the resource file inline. Never returns an attachment."""
        resource = self.get_object()
        if not can_view_resource(request.user, resource):
            return Response(
                {'detail': 'You do not have permission to access this material.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        DigitalResourceAccess.objects.create(
            resource=resource,
            user=request.user,
            action='view',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        return protected_file_response(
            resource.file, request=request, filename=resource.title,
        )

    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        """Record an access intent for a digital resource.

        Downloads are disabled by default. When they are enabled this returns
        the file URL; otherwise it refuses and points clients at the viewer.
        """
        resource = self.get_object()
        if not can_view_resource(request.user, resource):
            return Response(
                {'detail': 'You do not have permission to access this material.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DigitalResourceDownloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        requested_action = serializer.validated_data['action']
        if requested_action == 'download' and not material_downloads_allowed():
            return Response(
                {
                    'detail': 'Downloading is disabled on this platform.',
                    'file_url': resource.file_view_url,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        DigitalResourceAccess.objects.create(
            resource=resource,
            user=request.user,
            action=requested_action,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        if requested_action == 'download':
            resource.increment_download_count()

        return Response({
            'message': f'Resource {requested_action} logged successfully',
            'file_url': resource.file_view_url,
        })

class BookBorrowingViewSet(viewsets.ModelViewSet):
    """API viewset for BookBorrowing model"""
    queryset = BookBorrowing.objects.all()
    serializer_class = BookBorrowingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['book', 'borrower', 'is_active']
    ordering_fields = ['borrowed_date', 'due_date', 'return_date']
    ordering = ['-borrowed_date']

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        """Return a borrowed book"""
        borrowing = self.get_object()
        serializer = BookReturnActionSerializer(data=request.data)
        
        if serializer.is_valid():
            return_notes = serializer.validated_data.get('return_notes', '')
            
            borrowing.return_book(request.user)
            borrowing.notes += f"\nReturn notes: {return_notes}"
            borrowing.save()
            
            return Response({
                'message': 'Book returned successfully',
                'late_fee': float(borrowing.late_fee)
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookReservationViewSet(viewsets.ModelViewSet):
    """API viewset for BookReservation model"""
    queryset = BookReservation.objects.all()
    serializer_class = BookReservationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['book', 'user', 'status']
    ordering_fields = ['reservation_date', 'expiry_date']
    ordering = ['-reservation_date']

class LibraryStatisticsViewSet(viewsets.ViewSet):
    """API viewset for library statistics"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get library dashboard statistics"""
        today = timezone.now().date()
        
        # Basic statistics
        total_books = Book.objects.filter(is_active=True).count()
        available_books = Book.objects.filter(availability='available', is_active=True).count()
        borrowed_books = Book.objects.filter(availability='borrowed', is_active=True).count()
        overdue_books = BookBorrowing.objects.filter(
            due_date__lt=timezone.now(),
            return_date__isnull=True
        ).count()
        
        total_digital_resources = DigitalResource.objects.filter(is_active=True).count()
        total_borrowings_today = BookBorrowing.objects.filter(borrowed_date__date=today).count()
        total_returns_today = BookBorrowing.objects.filter(return_date__date=today).count()
        total_digital_access_today = DigitalResourceAccess.objects.filter(access_date__date=today).count()
        
        # Most borrowed books (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        most_borrowed = BookBorrowing.objects.filter(
            borrowed_date__gte=thirty_days_ago
        ).values('book__title').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Most accessed digital resources (last 30 days)
        most_accessed = DigitalResourceAccess.objects.filter(
            access_date__gte=thirty_days_ago
        ).values('resource__title').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        data = {
            'total_books': total_books,
            'available_books': available_books,
            'borrowed_books': borrowed_books,
            'overdue_books': overdue_books,
            'total_digital_resources': total_digital_resources,
            'total_borrowings_today': total_borrowings_today,
            'total_returns_today': total_returns_today,
            'total_digital_access_today': total_digital_access_today,
            'most_borrowed_books': list(most_borrowed),
            'most_accessed_resources': list(most_accessed)
        }
        
        serializer = LibraryStatisticsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def user_activity(self, request):
        """Get user library activity"""
        user = request.user
        
        current_borrowings = BookBorrowing.objects.filter(
            borrower=user,
            return_date__isnull=True
        ).count()
        
        overdue_books = BookBorrowing.objects.filter(
            borrower=user,
            due_date__lt=timezone.now(),
            return_date__isnull=True
        ).count()
        
        total_late_fees = BookBorrowing.objects.filter(
            borrower=user
        ).aggregate(total=Sum('late_fee'))['total'] or 0
        
        current_reservations = BookReservation.objects.filter(
            user=user,
            status='pending'
        ).count()
        
        total_digital_downloads = DigitalResourceAccess.objects.filter(
            user=user,
            action='download'
        ).count()
        
        # Recent activity
        recent_activity = []
        
        # Recent borrowings
        recent_borrowings = BookBorrowing.objects.filter(
            borrower=user
        ).order_by('-borrowed_date')[:5]
        
        for borrowing in recent_borrowings:
            recent_activity.append({
                'type': 'borrowing',
                'date': borrowing.borrowed_date,
                'title': borrowing.book.title,
                'action': 'borrowed' if not borrowing.return_date else 'returned'
            })
        
        # Recent digital access
        recent_access = DigitalResourceAccess.objects.filter(
            user=user
        ).order_by('-access_date')[:5]
        
        for access in recent_access:
            recent_activity.append({
                'type': 'digital',
                'date': access.access_date,
                'title': access.resource.title,
                'action': access.action
            })
        
        # Sort by date
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        recent_activity = recent_activity[:10]
        
        data = {
            'user': UserSerializer(user).data,
            'current_borrowings': current_borrowings,
            'overdue_books': overdue_books,
            'total_late_fees': float(total_late_fees),
            'current_reservations': current_reservations,
            'total_digital_downloads': total_digital_downloads,
            'recent_activity': recent_activity
        }
        
        serializer = UserLibraryActivitySerializer(data)
        return Response(serializer.data)

# Web Views
class LibraryDashboardView(LoginRequiredMixin, TemplateView):
    """Library dashboard view"""
    template_name = 'library/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        
        # Basic statistics
        context['total_books'] = Book.objects.filter(is_active=True).count()
        context['available_books'] = Book.objects.filter(availability='available', is_active=True).count()
        context['borrowed_books'] = Book.objects.filter(availability='borrowed', is_active=True).count()
        context['overdue_books'] = BookBorrowing.objects.filter(
            due_date__lt=timezone.now(),
            return_date__isnull=True
        ).count()
        context['total_digital_resources'] = DigitalResource.objects.filter(is_active=True).count()
        
        # Today's activity
        context['borrowings_today'] = BookBorrowing.objects.filter(borrowed_date__date=today).count()
        context['returns_today'] = BookBorrowing.objects.filter(return_date__date=today).count()
        context['digital_access_today'] = DigitalResourceAccess.objects.filter(access_date__date=today).count()
        
        # Recent activity
        context['recent_borrowings'] = BookBorrowing.objects.select_related('book', 'borrower').order_by('-borrowed_date')[:5]
        context['recent_returns'] = BookBorrowing.objects.select_related('book', 'borrower').filter(
            return_date__isnull=False
        ).order_by('-return_date')[:5]
        context['recent_digital_access'] = DigitalResourceAccess.objects.select_related('resource', 'user').order_by('-access_date')[:5]
        
        # Overdue books
        context['overdue_borrowings'] = BookBorrowing.objects.select_related('book', 'borrower').filter(
            due_date__lt=timezone.now(),
            return_date__isnull=True
        ).order_by('due_date')[:10]
        
        return context

class BookListView(LoginRequiredMixin, ListView):
    """Book list view with search and filtering"""
    model = Book
    template_name = 'library/book_list.html'
    context_object_name = 'books'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Book.objects.select_related('category').prefetch_related('borrowings').filter(is_active=True)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(author__icontains=search) |
                Q(isbn__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filters
        category = self.request.GET.get('category_filter')
        if category:
            queryset = queryset.filter(category_id=category)
        
        availability = self.request.GET.get('availability_filter')
        if availability:
            queryset = queryset.filter(availability=availability)
        
        condition = self.request.GET.get('condition_filter')
        if condition:
            queryset = queryset.filter(condition=condition)
        
        return queryset.order_by('title')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = BookSearchForm(self.request.GET)
        context['categories'] = BookCategory.objects.filter(is_active=True)
        return context

class BookDetailView(LoginRequiredMixin, DetailView):
    """Book detail view"""
    model = Book
    template_name = 'library/book_detail_modern.html'
    context_object_name = 'book'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_borrowing'] = self.object.current_borrower
        context['borrowing_history'] = self.object.borrowings.select_related('borrower').order_by('-borrowed_date')[:10]
        context['reservations'] = self.object.reservations.select_related('user').filter(status='pending')
        return context

class BookCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Book create view"""
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    success_url = reverse_lazy('library:book_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Book created successfully.')
        return response

class BookUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Book update view"""
    model = Book
    form_class = BookForm
    template_name = 'library/book_form.html'
    
    def get_success_url(self):
        return reverse('library:book_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Book updated successfully.')
        return response

class BookDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Book delete view"""
    model = Book
    template_name = 'library/book_confirm_delete.html'
    success_url = reverse_lazy('library:book_list')
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(request, 'Book deleted successfully.')
        return response

class DigitalResourceListView(LoginRequiredMixin, ListView):
    """Digital resource list view"""
    model = DigitalResource
    template_name = 'library/digital_resource_list.html'
    context_object_name = 'resources'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = DigitalResource.objects.filter(is_active=True)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(author__icontains=search) |
                Q(subject__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filters
        resource_type = self.request.GET.get('resource_type_filter')
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        access_level = self.request.GET.get('access_level_filter')
        if access_level:
            queryset = queryset.filter(access_level=access_level)
        
        subject = self.request.GET.get('subject_filter')
        if subject:
            queryset = queryset.filter(subject__icontains=subject)
        
        grade_level = self.request.GET.get('grade_level_filter')
        if grade_level:
            queryset = queryset.filter(grade_level__icontains=grade_level)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DigitalResourceSearchForm(self.request.GET)
        return context


class ResourceDiscoveryView(LoginRequiredMixin, ListView):
    model = DigitalResource
    template_name = 'library/resource_discovery.html'
    context_object_name = 'resources'
    paginate_by = 24

    def get_queryset(self):
        queryset = DigitalResource.objects.filter(is_active=True)
        user_type = getattr(self.request.user, 'user_type', '')
        if user_type == 'student':
            queryset = queryset.filter(access_level__in=['public', 'students'])
        elif user_type == 'teacher':
            queryset = queryset.filter(access_level__in=['public', 'students', 'teachers'])
        elif not is_admin_user(self.request.user):
            queryset = queryset.filter(access_level='public')

        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) | Q(subject__icontains=q) | Q(description__icontains=q)
            )
        return queryset.order_by('-created_at')


class TeacherResourceWorkspaceView(LoginRequiredMixin, AcademicStaffRequiredMixin, TemplateView):
    template_name = 'library/teacher_resource_workspace.html'

    def get_queryset(self):
        queryset = DigitalResource.objects.filter(is_active=True).select_related('uploaded_by')
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(uploaded_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resources = self.get_queryset()
        access_logs = DigitalResourceAccess.objects.filter(resource__in=resources)
        context.update({
            'resources': resources.order_by('-created_at')[:25],
            'total_resources': resources.count(),
            'student_resources': resources.filter(access_level='students').count(),
            'teacher_resources': resources.filter(access_level='teachers').count(),
            'total_downloads': resources.aggregate(total=Sum('current_downloads'))['total'] or 0,
            'recent_access': access_logs.select_related('resource', 'user').order_by('-access_date')[:10],
        })
        return context


class TeacherResourceUploadView(LoginRequiredMixin, AcademicStaffRequiredMixin, CreateView):
    model = DigitalResource
    form_class = DigitalResourceUploadForm
    template_name = 'library/teacher_resource_upload.html'
    success_url = reverse_lazy('library:teacher_resource_workspace')

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, 'Learning resource uploaded successfully.')
        return super().form_valid(form)


class DigitalResourceDetailView(LoginRequiredMixin, DetailView):
    """Digital resource detail view"""
    model = DigitalResource
    template_name = 'library/digital_resource_detail_modern.html'
    context_object_name = 'resource'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if is_admin_user(self.request.user):
            return queryset
        return queryset.filter(
            is_active=True,
            access_level__in=self._visible_access_levels(),
        )
    
    def _visible_access_levels(self):
        user_type = getattr(self.request.user, 'user_type', '')
        if user_type == 'student':
            return ['public', 'students']
        if user_type == 'teacher':
            return ['public', 'students', 'teachers']
        return ['public']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        access_logs = self.object.access_logs.select_related('user')
        context['access_logs'] = access_logs.order_by('-access_date')[:10]
        context['course_links'] = self.object.course_links.select_related('recommended_by')
        context['can_view_file'] = can_view_resource(self.request.user, self.object)
        context['can_manage'] = can_manage_resources(self.request.user)
        context['view_count'] = access_logs.filter(action='view').count()
        return context

class DigitalResourceCreateView(LoginRequiredMixin, AcademicStaffRequiredMixin, CreateView):
    """Digital resource create view (admins and teachers only)"""
    model = DigitalResource
    form_class = DigitalResourceForm
    template_name = 'library/digital_resource_form.html'
    success_url = reverse_lazy('library:digital_resource_list')
    
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Digital resource uploaded successfully.')
        return response

class DigitalResourceUpdateView(LoginRequiredMixin, AcademicStaffRequiredMixin, UpdateView):
    """Digital resource update view (admins and teachers only)"""
    model = DigitalResource
    form_class = DigitalResourceForm
    template_name = 'library/digital_resource_form.html'
    
    def get_queryset(self):
        # Teachers may only edit material they uploaded.
        queryset = super().get_queryset().filter(is_active=True)
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(uploaded_by=self.request.user)
        return queryset
    
    def get_success_url(self):
        return reverse('library:digital_resource_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Digital resource updated successfully.')
        return response

class DigitalResourceDeleteView(LoginRequiredMixin, AcademicStaffRequiredMixin, DeleteView):
    """Digital resource delete view (admins and teachers only)"""
    model = DigitalResource
    template_name = 'library/digital_resource_confirm_delete.html'
    success_url = reverse_lazy('library:digital_resource_list')
    context_object_name = 'resource'
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(is_active=True)
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(uploaded_by=self.request.user)
        return queryset
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(request, 'Digital resource deleted successfully.')
        return response

class BookBorrowingListView(LoginRequiredMixin, ListView):
    """Book borrowing list view"""
    model = BookBorrowing
    template_name = 'library/borrowing_list.html'
    context_object_name = 'borrowings'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = BookBorrowing.objects.select_related('book', 'borrower').order_by('-borrowed_date')
        
        # Filter by user unless administrator.
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(borrower=self.request.user)
        
        return queryset

class BookBorrowingCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Book borrowing create view"""
    model = BookBorrowing
    form_class = BookBorrowingForm
    template_name = 'library/borrowing_form.html'
    success_url = reverse_lazy('library:borrowing_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Update book availability
        book = form.instance.book
        book.availability = 'borrowed'
        book.save()
        
        messages.success(self.request, 'Book borrowed successfully.')
        return response

@login_required
@user_passes_test(is_admin_user)
def return_book(request, borrowing_id):
    """Return a borrowed book"""
    borrowing = get_object_or_404(BookBorrowing, id=borrowing_id)
    
    if request.method == 'POST':
        form = BookReturnForm(request.POST)
        if form.is_valid():
            return_notes = form.cleaned_data.get('return_notes', '')
            
            borrowing.return_book(request.user)
            if return_notes:
                borrowing.notes += f"\nReturn notes: {return_notes}"
                borrowing.save()
            
            messages.success(request, 'Book returned successfully.')
            return redirect('library:borrowing_list')
    else:
        form = BookReturnForm()
    
    return render(request, 'library/return_book.html', {
        'borrowing': borrowing,
        'form': form
    })

class BookReservationListView(LoginRequiredMixin, ListView):
    """Book reservation list view"""
    model = BookReservation
    template_name = 'library/reservation_list.html'
    context_object_name = 'reservations'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = BookReservation.objects.select_related('book', 'user').order_by('-reservation_date')
        
        # Filter by user unless administrator.
        if not is_admin_user(self.request.user):
            queryset = queryset.filter(user=self.request.user)
        
        return queryset

class BookReservationCreateView(LoginRequiredMixin, CreateView):
    """Book reservation create view"""
    model = BookReservation
    form_class = BookReservationForm
    template_name = 'library/reservation_form.html'
    success_url = reverse_lazy('library:reservation_list')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        # Set expiry date
        settings = LibrarySettings.get_settings()
        form.instance.expiry_date = timezone.now() + timedelta(hours=settings.reservation_duration_hours)
        
        response = super().form_valid(form)
        messages.success(self.request, 'Book reserved successfully.')
        return response

@login_required
def cancel_reservation(request, reservation_id):
    """Cancel a book reservation"""
    reservation = get_object_or_404(BookReservation, id=reservation_id, user=request.user)
    
    if request.method == 'POST':
        reservation.cancel_reservation()
        messages.success(request, 'Reservation cancelled successfully.')
        return redirect('library:reservation_list')
    
    return render(request, 'library/cancel_reservation.html', {
        'reservation': reservation
    })

@login_required
def download_resource(request, resource_id):
    """Download a digital resource.

    Downloads are disabled by default (ALLOW_MATERIAL_DOWNLOADS=False). The
    route is kept so stale links fail loudly instead of 404ing, and so an
    operator can re-enable downloads with a single setting.
    """
    resource = get_object_or_404(DigitalResource, id=resource_id, is_active=True)

    if not can_view_resource(request.user, resource):
        messages.error(request, 'You do not have permission to access this resource.')
        return redirect('library:digital_resource_list')

    if not material_downloads_allowed():
        messages.error(
            request,
            'Downloading is disabled on this platform. Use "View" to read this material instead.',
        )
        return redirect('library:digital_resource_detail', pk=resource.pk)

    DigitalResourceAccess.objects.create(
        resource=resource,
        user=request.user,
        action='download',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    resource.increment_download_count()

    return protected_file_response(
        resource.file, request=request, filename=resource.title, attachment=True,
    )


@login_required
def view_resource_file(request, resource_id):
    """Stream a digital resource inline to an authorised, signed-in user."""
    resource = get_object_or_404(DigitalResource, id=resource_id, is_active=True)

    if not can_view_resource(request.user, resource):
        raise PermissionDenied('You do not have permission to access this material.')

    DigitalResourceAccess.objects.create(
        resource=resource,
        user=request.user,
        action='view',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )

    return protected_file_response(
        resource.file, request=request, filename=resource.title,
    )

@login_required
@user_passes_test(is_admin_user)
def barcode_scan(request):
    """Barcode scanning interface"""
    if request.method == 'POST':
        form = BookBarcodeScanForm(request.POST)
        if form.is_valid():
            barcode = form.cleaned_data['barcode']
            try:
                book = Book.objects.get(barcode=barcode, is_active=True)
                return redirect('library:book_detail', pk=book.pk)
            except Book.DoesNotExist:
                messages.error(request, 'Book not found with this barcode.')
    else:
        form = BookBarcodeScanForm()
    
    return render(request, 'library/barcode_scan.html', {'form': form})

@login_required
@user_passes_test(is_admin_user)
def bulk_import_books(request):
    """Bulk import books from CSV"""
    if request.method == 'POST':
        form = BulkBookImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            category_mapping = form.cleaned_data.get('category_mapping', '')
            
            # Parse category mapping
            category_map = {}
            if category_mapping:
                for mapping in category_mapping.split(','):
                    if ':' in mapping:
                        csv_cat, existing_cat = mapping.strip().split(':', 1)
                        category_map[csv_cat.strip()] = existing_cat.strip()
            
            # Process CSV
            try:
                decoded_file = csv_file.read().decode('utf-8')
                csv_data = csv.DictReader(io.StringIO(decoded_file))
                
                imported_count = 0
                for row in csv_data:
                    # Get or create category
                    category_name = row.get('category', '').strip()
                    if category_name in category_map:
                        category_name = category_map[category_name]
                    
                    category, created = BookCategory.objects.get_or_create(
                        name=category_name,
                        defaults={'description': f'Imported category: {category_name}'}
                    )
                    
                    # Create book
                    book_data = {
                        'title': row.get('title', '').strip(),
                        'author': row.get('author', '').strip(),
                        'isbn': row.get('isbn', '').strip() or None,
                        'category': category,
                        'edition': row.get('edition', '').strip(),
                        'publisher': row.get('publisher', '').strip(),
                        'publication_year': int(row.get('publication_year', 0)) if row.get('publication_year') else None,
                        'pages': int(row.get('pages', 0)) if row.get('pages') else None,
                        'description': row.get('description', '').strip(),
                        'location': row.get('location', '').strip(),
                        'price': float(row.get('price', 0)) if row.get('price') else None,
                    }
                    
                    # Remove None values
                    book_data = {k: v for k, v in book_data.items() if v is not None}
                    
                    Book.objects.create(**book_data)
                    imported_count += 1
                
                messages.success(request, f'Successfully imported {imported_count} books.')
                return redirect('library:book_list')
                
            except Exception as e:
                messages.error(request, f'Error importing books: {str(e)}')
    else:
        form = BulkBookImportForm()
    
    return render(request, 'library/bulk_import.html', {'form': form})

@login_required
@user_passes_test(is_admin_user)
def library_reports(request):
    """Library reports view"""
    # Generate today's report if it doesn't exist
    today = timezone.now().date()
    report, created = LibraryReport.objects.get_or_create(
        report_type='daily',
        report_date=today,
        defaults=LibraryReport.generate_daily_report(today).__dict__
    )
    
    # Get recent reports
    recent_reports = LibraryReport.objects.order_by('-report_date')[:30]
    
    return render(request, 'library/reports.html', {
        'today_report': report,
        'recent_reports': recent_reports
    })

@login_required
@user_passes_test(is_admin_user)
def library_settings(request):
    """Library settings view"""
    settings = LibrarySettings.get_settings()
    
    if request.method == 'POST':
        form = LibrarySettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Library settings updated successfully.')
            return redirect('library:settings')
    else:
        form = LibrarySettingsForm(instance=settings)
    
    return render(request, 'library/settings.html', {'form': form})
