from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'accounts'


router = DefaultRouter()
router.register(r'institutions', views.InstitutionViewSet, basename='institution')
router.register(r'institution-memberships', views.InstitutionMembershipViewSet, basename='institution-membership')
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.UserProfileViewSet)
router.register(r'roles', views.RoleViewSet)
router.register(r'permissions', views.PermissionViewSet)

urlpatterns = [
    # API URLs
    path('api/', include(router.urls)),
    
    # Web URLs
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('ai-hub/', views.AIHubView.as_view(), name='ai_hub'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileView.as_view(), name='profile_edit'),
    path('password/change/', views.ProfileView.as_view(), name='password_change'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('register/teacher/', views.TeacherRegisterView.as_view(), name='teacher_register'),
    path('register/institution/', views.InstitutionRegisterView.as_view(), name='institution_register'),
    
    # Handle Allauth profile redirect
    path('accounts/profile/', views.ProfileView.as_view(), name='allauth_profile'),
]
