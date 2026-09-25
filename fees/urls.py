from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'fees'

# API Router
router = DefaultRouter()
router.register(r'categories', views.FeeCategoryViewSet)
router.register(r'structures', views.FeeStructureViewSet)
router.register(r'structure-details', views.FeeStructureDetailViewSet)
router.register(r'student-fees', views.StudentFeeViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'receipts', views.ReceiptViewSet)
router.register(r'discounts', views.FeeDiscountViewSet)
router.register(r'student-discounts', views.StudentFeeDiscountViewSet)

# API URLs
api_urls = [
    path('api/', include(router.urls)),
]

# Web URLs
urlpatterns = [
    # Dashboard
    path('', views.fees_dashboard, name='dashboard'),
    path('my/', views.MyFeesView.as_view(), name='my_fees'),
    
    # Student Fees
    path('student-fees/', views.StudentFeeListView.as_view(), name='student_fee_list'),
    path('student-fees/create/', views.StudentFeeCreateView.as_view(), name='student_fee_create'),
    path('student-fees/<int:pk>/', views.StudentFeeDetailView.as_view(), name='student_fee_detail'),
    path('student-fees/<int:pk>/update/', views.StudentFeeUpdateView.as_view(), name='student_fee_update'),
    
    # Payments
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/create/', views.PaymentCreateView.as_view(), name='payment_create'),
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('receipts/', views.ReceiptListView.as_view(), name='receipt_list'),
    path('receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='receipt_detail'),
    
    # Bulk Operations
    path('bulk-fee-generation/', views.bulk_fee_generation, name='bulk_fee_generation'),
    path('bulk-payment/', views.bulk_payment, name='bulk_payment'),
    
    # Reports
    path('reports/', views.fee_report, name='fee_report'),
    
    # AJAX endpoints
    path('ajax/get-students-for-fee-structure/', views.get_students_for_fee_structure, name='get_students_for_fee_structure'),
    path('ajax/get-student-fees/', views.get_student_fees, name='get_student_fees'),
]

# Include API URLs
urlpatterns += api_urls
