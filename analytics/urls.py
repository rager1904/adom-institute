from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'events', views.AnalyticsEventViewSet)
router.register(r'student-performance', views.StudentPerformanceViewSet)
router.register(r'class-performance', views.ClassPerformanceViewSet)
router.register(r'teacher-performance', views.TeacherPerformanceViewSet)
router.register(r'school-analytics', views.SchoolAnalyticsViewSet)
router.register(r'reports', views.ReportViewSet)

app_name = 'analytics'

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Web URLs
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('my-analytics/', views.MyAnalyticsView.as_view(), name='my_analytics'),
    path('student-performance/', views.StudentPerformanceListView.as_view(), name='student_performance_list'),
    path('class-performance/', views.ClassPerformanceListView.as_view(), name='class_performance_list'),
    path('teacher-performance/', views.TeacherPerformanceListView.as_view(), name='teacher_performance_list'),
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ReportCreateView.as_view(), name='report_create'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('reports/<int:pk>/update/', views.ReportUpdateView.as_view(), name='report_update'),
    path('reports/<int:pk>/delete/', views.ReportDeleteView.as_view(), name='report_delete'),
]
