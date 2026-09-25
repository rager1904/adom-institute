from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.http import JsonResponse
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Room, TimeSlot, ClassSchedule, TeacherSchedule, RoomSchedule, AcademicCalendar
from .forms import (
    RoomForm, TimeSlotForm, ClassScheduleForm, TeacherScheduleForm, 
    RoomScheduleForm, AcademicCalendarForm, RoomSearchForm, ClassScheduleSearchForm
)
from django.utils import timezone
from accounts.permissions import AdminRequiredMixin, is_platform_admin, user_institution_ids


def scope_schedules_for_user(user, queryset):
    if is_platform_admin(user):
        return queryset
    if user.user_type == 'student':
        return queryset.filter(class_obj__students__user=user)
    if user.user_type == 'parent':
        return queryset.filter(class_obj__students__parents__user=user)
    if user.user_type == 'teacher':
        return queryset.filter(teacher__user=user)
    institution_ids = user_institution_ids(user)
    return queryset.filter(class_obj__academic_year__institution_id__in=institution_ids) if institution_ids else queryset.none()


# API Viewsets
class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = None  # Will be defined when DRF is properly set up
    permission_classes = [permissions.IsAuthenticated]


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.all()
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]


class ClassScheduleViewSet(viewsets.ModelViewSet):
    queryset = ClassSchedule.objects.all()
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]


# Web Views
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'timetable/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        schedules = scope_schedules_for_user(
            self.request.user,
            ClassSchedule.objects.select_related('class_obj', 'subject', 'teacher', 'room', 'time_slot')
        )
        context['total_rooms'] = schedules.values('room').distinct().count()
        context['active_rooms'] = schedules.filter(room__is_active=True).values('room').distinct().count()
        context['total_schedules'] = schedules.count()
        context['active_schedules'] = schedules.filter(is_active=True).count()
        context['total_events'] = AcademicCalendar.objects.count()
        context['upcoming_events'] = AcademicCalendar.objects.filter(
            start_date__gte=timezone.now().date()
        ).count()
        
        # Recent schedules
        context['recent_schedules'] = schedules.order_by('-created_at')[:5]
        
        # Room type distribution
        context['room_types'] = Room.objects.filter(schedules__in=schedules).values('room_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return context


class RoomListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Room
    template_name = 'timetable/room_list.html'
    context_object_name = 'rooms'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Room.objects.all()
        search_form = RoomSearchForm(self.request.GET)
        
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            room_type = search_form.cleaned_data.get('room_type_filter')
            
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(building__icontains=search) |
                    Q(description__icontains=search)
                )
            
            if room_type:
                queryset = queryset.filter(room_type=room_type)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = RoomSearchForm(self.request.GET)
        return context


class RoomDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = Room
    template_name = 'timetable/room_detail.html'
    context_object_name = 'room'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedules'] = self.object.schedules.select_related(
            'class_obj', 'subject', 'teacher', 'time_slot'
        ).order_by('time_slot__day', 'time_slot__start_time')
        return context


class RoomCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Room
    form_class = RoomForm
    template_name = 'timetable/room_form.html'
    success_url = reverse_lazy('timetable:room_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Room created successfully!')
        return super().form_valid(form)


class RoomUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Room
    form_class = RoomForm
    template_name = 'timetable/room_form.html'
    success_url = reverse_lazy('timetable:room_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Room updated successfully!')
        return super().form_valid(form)


class RoomDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Room
    template_name = 'timetable/room_confirm_delete.html'
    success_url = reverse_lazy('timetable:room_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Room deleted successfully!')
        return super().delete(request, *args, **kwargs)


class TimeSlotListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = TimeSlot
    template_name = 'timetable/timeslot_list.html'
    context_object_name = 'timeslots'
    paginate_by = 20
    ordering = ['day', 'start_time']


class TimeSlotDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    model = TimeSlot
    template_name = 'timetable/timeslot_detail.html'
    context_object_name = 'timeslot'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schedules'] = self.object.schedules.select_related(
            'class_obj', 'subject', 'teacher', 'room'
        )
        return context


class TimeSlotCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = 'timetable/timeslot_form.html'
    success_url = reverse_lazy('timetable:timeslot_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Time slot created successfully!')
        return super().form_valid(form)


class TimeSlotUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = TimeSlot
    form_class = TimeSlotForm
    template_name = 'timetable/timeslot_form.html'
    success_url = reverse_lazy('timetable:timeslot_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Time slot updated successfully!')
        return super().form_valid(form)


class TimeSlotDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = TimeSlot
    template_name = 'timetable/timeslot_confirm_delete.html'
    success_url = reverse_lazy('timetable:timeslot_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Time slot deleted successfully!')
        return super().delete(request, *args, **kwargs)


class ClassScheduleListView(LoginRequiredMixin, ListView):
    model = ClassSchedule
    template_name = 'timetable/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ClassSchedule.objects.select_related(
            'class_obj', 'subject', 'teacher', 'room', 'time_slot'
        )
        queryset = scope_schedules_for_user(self.request.user, queryset)
        search_form = ClassScheduleSearchForm(self.request.GET)
        
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            day = search_form.cleaned_data.get('day_filter')
            
            if search:
                queryset = queryset.filter(
                    Q(class_obj__name__icontains=search) |
                    Q(subject__name__icontains=search) |
                    Q(teacher__user__first_name__icontains=search) |
                    Q(teacher__user__last_name__icontains=search) |
                    Q(room__name__icontains=search)
                )
            
            if day:
                queryset = queryset.filter(time_slot__day=day)
        
        return queryset.distinct().order_by('time_slot__day', 'time_slot__start_time')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ClassScheduleSearchForm(self.request.GET)
        return context


class ClassScheduleDetailView(LoginRequiredMixin, DetailView):
    model = ClassSchedule
    template_name = 'timetable/schedule_detail.html'
    context_object_name = 'schedule'

    def get_queryset(self):
        queryset = ClassSchedule.objects.select_related(
            'class_obj', 'subject', 'teacher__user', 'room', 'time_slot'
        )
        return scope_schedules_for_user(self.request.user, queryset).distinct()


class ClassScheduleCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = ClassSchedule
    form_class = ClassScheduleForm
    template_name = 'timetable/schedule_form.html'
    success_url = reverse_lazy('timetable:schedule_list')
    
    def form_valid(self, form):
        try:
            form.instance.full_clean()
            messages.success(self.request, 'Schedule created successfully!')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error creating schedule: {str(e)}')
            return self.form_invalid(form)


class ClassScheduleUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = ClassSchedule
    form_class = ClassScheduleForm
    template_name = 'timetable/schedule_form.html'
    success_url = reverse_lazy('timetable:schedule_list')
    
    def form_valid(self, form):
        try:
            form.instance.full_clean()
            messages.success(self.request, 'Schedule updated successfully!')
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f'Error updating schedule: {str(e)}')
            return self.form_invalid(form)


class ClassScheduleDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = ClassSchedule
    template_name = 'timetable/schedule_confirm_delete.html'
    success_url = reverse_lazy('timetable:schedule_list')
    context_object_name = 'schedule'

    def get_queryset(self):
        queryset = ClassSchedule.objects.select_related(
            'class_obj', 'subject', 'teacher', 'room', 'time_slot'
        )
        return scope_schedules_for_user(self.request.user, queryset).distinct()
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Schedule deleted successfully!')
        return super().delete(request, *args, **kwargs)


class AcademicCalendarListView(LoginRequiredMixin, ListView):
    model = AcademicCalendar
    template_name = 'timetable/calendar_list.html'
    context_object_name = 'events'
    paginate_by = 20
    ordering = ['start_date']


class AcademicCalendarDetailView(LoginRequiredMixin, DetailView):
    model = AcademicCalendar
    template_name = 'timetable/calendar_detail.html'
    context_object_name = 'event'


class AcademicCalendarCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = AcademicCalendar
    form_class = AcademicCalendarForm
    template_name = 'timetable/calendar_form.html'
    success_url = reverse_lazy('timetable:calendar_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Event created successfully!')
        return super().form_valid(form)


class AcademicCalendarUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = AcademicCalendar
    form_class = AcademicCalendarForm
    template_name = 'timetable/calendar_form.html'
    success_url = reverse_lazy('timetable:calendar_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Event updated successfully!')
        return super().form_valid(form)


class AcademicCalendarDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = AcademicCalendar
    template_name = 'timetable/calendar_confirm_delete.html'
    success_url = reverse_lazy('timetable:calendar_list')
    context_object_name = 'event'
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Event deleted successfully!')
        return super().delete(request, *args, **kwargs)

# Additional utility views
class TimetableView(LoginRequiredMixin, TemplateView):
    template_name = 'timetable/timetable_view.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all schedules grouped by day
        schedules = ClassSchedule.objects.select_related(
            'class_obj', 'subject', 'teacher', 'room', 'time_slot'
        ).filter(is_active=True).order_by('time_slot__day', 'time_slot__start_time')
        schedules = scope_schedules_for_user(self.request.user, schedules).distinct()
        
        # Group by day
        days = {}
        for schedule in schedules:
            day = schedule.time_slot.day
            if day not in days:
                days[day] = []
            days[day].append(schedule)
        
        context['days'] = days
        context['all_days'] = TimeSlot.DayOfWeek.choices
        context['day_sections'] = [
            {
                'value': day_value,
                'label': day_label,
                'schedules': days.get(day_value, []),
            }
            for day_value, day_label in TimeSlot.DayOfWeek.choices
        ]
        context['schedule_count'] = sum(len(day_schedules) for day_schedules in days.values())
        return context


def get_schedule_conflicts(request):
    """API endpoint to check for schedule conflicts"""
    if request.method == 'GET':
        teacher_id = request.GET.get('teacher_id')
        room_id = request.GET.get('room_id')
        time_slot_id = request.GET.get('time_slot_id')
        schedule_id = request.GET.get('schedule_id')
        
        conflicts = []
        
        if teacher_id and time_slot_id:
            teacher_conflicts = ClassSchedule.objects.filter(
                teacher_id=teacher_id,
                time_slot_id=time_slot_id,
                is_active=True
            ).exclude(id=schedule_id)
            
            if teacher_conflicts.exists():
                conflicts.append('Teacher conflict')
        
        if room_id and time_slot_id:
            room_conflicts = ClassSchedule.objects.filter(
                room_id=room_id,
                time_slot_id=time_slot_id,
                is_active=True
            ).exclude(id=schedule_id)
            
            if room_conflicts.exists():
                conflicts.append('Room conflict')
        
        return JsonResponse({'conflicts': conflicts})
    
    return JsonResponse({'error': 'Invalid request method'})

