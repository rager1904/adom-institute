from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'library'

# API Router
router = DefaultRouter()
router.register(r'books', views.BookViewSet)
router.register(r'categories', views.BookCategoryViewSet)
router.register(r'digital-resources', views.DigitalResourceViewSet)
router.register(r'borrowings', views.BookBorrowingViewSet)
router.register(r'reservations', views.BookReservationViewSet)
router.register(r'statistics', views.LibraryStatisticsViewSet, basename='statistics')

# API URLs
api_urlpatterns = [
    path('api/', include(router.urls)),
]

# Web URLs
urlpatterns = [
    # Dashboard
    path('', views.LibraryDashboardView.as_view(), name='dashboard'),
    
    # Books
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/create/', views.BookCreateView.as_view(), name='book_create'),
    path('books/<int:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('books/<int:pk>/edit/', views.BookUpdateView.as_view(), name='book_update'),
    path('books/<int:pk>/delete/', views.BookDeleteView.as_view(), name='book_delete'),
    
    # Digital Resources
    path('discover/', views.ResourceDiscoveryView.as_view(), name='resource_discovery'),
    path('resources/', views.TeacherResourceWorkspaceView.as_view(), name='teacher_resource_workspace'),
    path('resources/upload/', views.TeacherResourceUploadView.as_view(), name='teacher_resource_upload'),
    path('digital-resources/', views.DigitalResourceListView.as_view(), name='digital_resource_list'),
    path('digital-resources/create/', views.DigitalResourceCreateView.as_view(), name='digital_resource_create'),
    path('digital-resources/<int:pk>/', views.DigitalResourceDetailView.as_view(), name='digital_resource_detail'),
    path('digital-resources/<int:pk>/edit/', views.DigitalResourceUpdateView.as_view(), name='digital_resource_update'),
    path('digital-resources/<int:pk>/delete/', views.DigitalResourceDeleteView.as_view(), name='digital_resource_delete'),
    path('digital-resources/<int:resource_id>/download/', views.download_resource, name='download_resource'),
    
    # Borrowings
    path('borrowings/', views.BookBorrowingListView.as_view(), name='borrowing_list'),
    path('borrowings/create/', views.BookBorrowingCreateView.as_view(), name='borrowing_create'),
    path('borrowings/<int:borrowing_id>/return/', views.return_book, name='return_book'),
    
    # Reservations
    path('reservations/', views.BookReservationListView.as_view(), name='reservation_list'),
    path('reservations/create/', views.BookReservationCreateView.as_view(), name='reservation_create'),
    path('reservations/<int:reservation_id>/cancel/', views.cancel_reservation, name='cancel_reservation'),
    
    # Tools
    path('barcode-scan/', views.barcode_scan, name='barcode_scan'),
    path('bulk-import/', views.bulk_import_books, name='bulk_import'),
    
    # Reports and Settings
    path('reports/', views.library_reports, name='reports'),
    path('settings/', views.library_settings, name='settings'),
]

# Include API URLs
urlpatterns += api_urlpatterns
