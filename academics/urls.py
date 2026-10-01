from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'exam-types', views.ExamTypeViewSet)
router.register(r'exams', views.ExamViewSet)
router.register(r'exam-subjects', views.ExamSubjectViewSet)
router.register(r'grades', views.GradeViewSet)
router.register(r'student-exam-results', views.StudentExamResultViewSet)
router.register(r'assignments', views.AssignmentViewSet)
router.register(r'student-assignments', views.StudentAssignmentViewSet)

app_name = 'academics'

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('my/', views.MyAcademicsView.as_view(), name='my_academics'),
    path('grading/', views.GradingQueueView.as_view(), name='grading_queue'),
    path('courses/', views.CourseListView.as_view(), name='course_list'),
    path('courses/<int:pk>/', views.CourseDetailView.as_view(), name='course_detail'),
    
    # Web URLs - Exams
    path('exams/', views.ExamListView.as_view(), name='exam_list'),
    path('exams/create/', views.ExamCreateView.as_view(), name='exam_create'),
    path('exams/<int:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),
    path('exams/<int:pk>/update/', views.ExamUpdateView.as_view(), name='exam_update'),
    path('exams/<int:pk>/delete/', views.ExamDeleteView.as_view(), name='exam_delete'),
    
    # Web URLs - Assignments
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/create/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignments/<int:pk>/update/', views.AssignmentUpdateView.as_view(), name='assignment_update'),
    path('assignments/<int:pk>/delete/', views.AssignmentDeleteView.as_view(), name='assignment_delete'),
    # Inline, authenticated viewer. The only route that reads a material file.
    path('assignments/<int:pk>/file/', views.assignment_file, name='assignment_file'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'),
    path('submissions/<int:pk>/file/', views.submission_file, name='submission_file'),
    
    # Web URLs - Student Assignments
    path('student-assignments/', views.StudentAssignmentListView.as_view(), name='student_assignment_list'),
    path('student-assignments/create/', views.StudentAssignmentCreateView.as_view(), name='student_assignment_create'),
    path('student-assignments/<int:pk>/', views.StudentAssignmentDetailView.as_view(), name='student_assignment_detail'),
    path('student-assignments/<int:pk>/update/', views.StudentAssignmentUpdateView.as_view(), name='student_assignment_update'),
]
