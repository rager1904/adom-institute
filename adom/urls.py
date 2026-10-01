"""
URL configuration for adom project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from adom.protected_media import serve_public_media
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from accounts.views import HomeView
from academics.urls import router as academics_router
from accounts.urls import router as accounts_router
from analytics.urls import router as analytics_router
from attendance.urls import router as attendance_router
from communication.urls import router as communication_router
from adom_institute.urls import router as adom_institute_router
from fees.urls import router as fees_router
from library.urls import router as library_router
from students.urls import router as students_router
from teachers.urls import router as teachers_router
from timetable.urls import router as timetable_router

schema_view = get_schema_view(
    openapi.Info(
        title="ADOM Institute API",
        default_version='v1',
        description="ADOM Institute AI-powered education management API",
        terms_of_service="https://www.adominstitute.com/terms/",
        contact=openapi.Contact(email="admin@adominstitute.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # Authentication - Using custom accounts app instead of allauth
    # path('accounts/', include('allauth.urls')),
    
    # API URLs
    path('api/v1/', include([
        path('accounts/', include((accounts_router.urls, 'accounts'), namespace='accounts_api')),
        path('students/', include((students_router.urls, 'students'), namespace='students_api')),
        path('teachers/', include((teachers_router.urls, 'teachers'), namespace='teachers_api')),
        path('academics/', include((academics_router.urls, 'academics'), namespace='academics_api')),
        path('fees/', include((fees_router.urls, 'fees'), namespace='fees_api')),
        path('attendance/', include((attendance_router.urls, 'attendance'), namespace='attendance_api')),
        path('communication/', include((communication_router.urls, 'communication'), namespace='communication_api')),
        path('timetable/', include((timetable_router.urls, 'timetable'), namespace='timetable_api')),
        path('library/', include((library_router.urls, 'library'), namespace='library_api')),
        path('analytics/', include((analytics_router.urls, 'analytics'), namespace='analytics_api')),
        path('adom-institute/', include((adom_institute_router.urls, 'adom_institute'), namespace='adom_institute_api')),
    ])),
    
    # Web URLs
    path('accounts/', include('accounts.urls')),
    path('students/', include('students.urls')),
    path('teachers/', include('teachers.urls')),
    path('academics/', include('academics.urls')),
    path('fees/', include('fees.urls')),
    path('attendance/', include('attendance.urls')),
    path('communication/', include('communication.urls')),
    path('timetable/', include('timetable.urls')),
    path('library/', include('library.urls')),
    path('analytics/', include('analytics.urls')),
    path('adom-institute/', include('adom_institute.urls')),
]

# Serve media files in development.
# Learning material is excluded on purpose: it is only reachable through the
# authenticated read-only viewer, never through the raw /media/ path.
if settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_public_media, name='media'),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
