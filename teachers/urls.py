from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'teachers'

router = DefaultRouter()
router.register(r'teachers', views.TeacherViewSet)
router.register(r'subjects', views.SubjectViewSet)
router.register(r'departments', views.DepartmentViewSet)

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('my/', views.MyTeachingView.as_view(), name='my_teaching'),
    path('class-subject-assignment/', views.TeacherClassSubjectAssignmentView.as_view(), name='class_subject_assignment'),
    
    # Teacher URLs
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/create/', views.TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<int:pk>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.TeacherUpdateView.as_view(), name='teacher_update'),
    path('teachers/<int:pk>/delete/', views.TeacherDeleteView.as_view(), name='teacher_delete'),
    
    # Subject URLs
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/create/', views.SubjectCreateView.as_view(), name='subject_create'),
    path('subjects/<int:pk>/', views.SubjectDetailView.as_view(), name='subject_detail'),
    path('subjects/<int:pk>/edit/', views.SubjectUpdateView.as_view(), name='subject_update'),
    path('subjects/<int:pk>/delete/', views.SubjectDeleteView.as_view(), name='subject_delete'),
    
    # Department URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department_delete'),
]
