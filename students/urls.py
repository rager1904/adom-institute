from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


app_name = 'students'

router = DefaultRouter()
router.register(r'academic-years', views.AcademicYearViewSet)
router.register(r'classes', views.ClassViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'parents', views.ParentViewSet)

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Web URLs
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('portal/', views.StudentPortalView.as_view(), name='student_portal'),
    
    # Student URLs
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/create/', views.StudentCreateView.as_view(), name='student_create'),
    path('students/<int:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/<int:pk>/edit/', views.StudentUpdateView.as_view(), name='student_update'),
    path('students/<int:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
    
    # Class URLs
    path('classes/', views.ClassListView.as_view(), name='class_list'),
    path('classes/create/', views.ClassCreateView.as_view(), name='class_create'),
    path('classes/<int:pk>/', views.ClassDetailView.as_view(), name='class_detail'),
    path('classes/<int:pk>/edit/', views.ClassUpdateView.as_view(), name='class_update'),
    path('classes/<int:pk>/delete/', views.ClassDeleteView.as_view(), name='class_delete'),
    path('class-placement/', views.StudentClassPlacementView.as_view(), name='class_placement'),
    
    # Parent URLs
    path('parents/', views.ParentListView.as_view(), name='parent_list'),
    path('parents/create/', views.ParentCreateView.as_view(), name='parent_create'),
    path('parents/<int:pk>/', views.ParentDetailView.as_view(), name='parent_detail'),
    path('parents/<int:pk>/edit/', views.ParentUpdateView.as_view(), name='parent_update'),
    path('parents/<int:pk>/delete/', views.ParentDeleteView.as_view(), name='parent_delete'),
    
    # AJAX URLs
    path('ajax/students-by-class/', views.get_students_by_class, name='get_students_by_class'),
    path('ajax/classes-by-academic-year/', views.get_classes_by_academic_year, name='get_classes_by_academic_year'),
    path('ajax/student-statistics/', views.student_statistics, name='student_statistics'),
]
