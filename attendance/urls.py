from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'attendance', views.AttendanceViewSet)
router.register(r'class-attendance', views.ClassAttendanceViewSet)
router.register(r'teacher-attendance', views.TeacherAttendanceViewSet)
router.register(r'leave-requests', views.LeaveRequestViewSet)

app_name = 'attendance'

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Web URLs
    path('', views.attendance_dashboard, name='dashboard'),
    path('my/', views.MyAttendanceView.as_view(), name='my_attendance'),
    path('list/', views.AttendanceListView.as_view(), name='attendance_list'),
    path('create/', views.AttendanceCreateView.as_view(), name='attendance_create'),
    path('bulk/', views.BulkAttendanceView.as_view(), name='bulk_attendance'),
    path('<int:pk>/', views.AttendanceDetailView.as_view(), name='attendance_detail'),
    path('<int:pk>/update/', views.AttendanceUpdateView.as_view(), name='attendance_update'),
    
    # Leave Request URLs
    path('leave/', views.LeaveRequestListView.as_view(), name='leave_request_list'),
    path('leave/create/', views.LeaveRequestCreateView.as_view(), name='leave_request_create'),
    path('leave/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),
    path('leave/<int:pk>/update/', views.LeaveRequestUpdateView.as_view(), name='leave_request_update'),
    path('leave/<int:pk>/approve/', views.LeaveApprovalView.as_view(), name='leave_approval'),
    
    # Reports
    path('report/', views.attendance_report, name='attendance_report'),
    
    # AJAX URLs
    path('ajax/students/', views.get_students_for_class, name='get_students_for_class'),
    path('ajax/mark-attendance/', views.mark_attendance_ajax, name='mark_attendance_ajax'),
]
