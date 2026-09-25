from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'timetable'

router = DefaultRouter()
router.register(r'rooms', views.RoomViewSet)
router.register(r'timeslots', views.TimeSlotViewSet)
router.register(r'schedules', views.ClassScheduleViewSet)

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('my-schedule/', views.TimetableView.as_view(), name='my_schedule'),
    
    # Room URLs
    path('rooms/', views.RoomListView.as_view(), name='room_list'),
    path('rooms/<int:pk>/', views.RoomDetailView.as_view(), name='room_detail'),
    path('rooms/create/', views.RoomCreateView.as_view(), name='room_create'),
    path('rooms/<int:pk>/update/', views.RoomUpdateView.as_view(), name='room_update'),
    path('rooms/<int:pk>/delete/', views.RoomDeleteView.as_view(), name='room_delete'),
    
    # TimeSlot URLs
    path('timeslots/', views.TimeSlotListView.as_view(), name='timeslot_list'),
    path('timeslots/<int:pk>/', views.TimeSlotDetailView.as_view(), name='timeslot_detail'),
    path('timeslots/create/', views.TimeSlotCreateView.as_view(), name='timeslot_create'),
    path('timeslots/<int:pk>/update/', views.TimeSlotUpdateView.as_view(), name='timeslot_update'),
    path('timeslots/<int:pk>/delete/', views.TimeSlotDeleteView.as_view(), name='timeslot_delete'),
    
    # ClassSchedule URLs
    path('schedules/', views.ClassScheduleListView.as_view(), name='schedule_list'),
    path('schedules/<int:pk>/', views.ClassScheduleDetailView.as_view(), name='schedule_detail'),
    path('schedules/create/', views.ClassScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/update/', views.ClassScheduleUpdateView.as_view(), name='schedule_update'),
    path('schedules/<int:pk>/delete/', views.ClassScheduleDeleteView.as_view(), name='schedule_delete'),
    
    # AcademicCalendar URLs
    path('calendar/', views.AcademicCalendarListView.as_view(), name='calendar_list'),
    path('calendar/<int:pk>/', views.AcademicCalendarDetailView.as_view(), name='calendar_detail'),
    path('calendar/create/', views.AcademicCalendarCreateView.as_view(), name='calendar_create'),
    path('calendar/<int:pk>/update/', views.AcademicCalendarUpdateView.as_view(), name='calendar_update'),
    path('calendar/<int:pk>/delete/', views.AcademicCalendarDeleteView.as_view(), name='calendar_delete'),
    
    # API URLs
    path('api/', include(router.urls)),
]
