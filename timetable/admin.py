from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Room, TimeSlot, ClassSchedule, TeacherSchedule, RoomSchedule, AcademicCalendar


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'room_type', 'capacity', 'building', 'floor', 'is_active', 'get_schedule_count']
    list_filter = ['room_type', 'is_active', 'building', 'floor']
    search_fields = ['name', 'building', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'room_type', 'capacity')
        }),
        ('Location', {
            'fields': ('building', 'floor')
        }),
        ('Additional Information', {
            'fields': ('description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_schedule_count(self, obj):
        count = obj.schedules.count()
        return format_html('<span class="badge bg-info">{}</span>', count)
    get_schedule_count.short_description = 'Schedules'


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['day', 'start_time', 'end_time', 'period_number', 'is_break', 'break_type', 'get_duration']
    list_filter = ['day', 'is_break', 'break_type']
    search_fields = ['day', 'break_type']
    list_editable = ['is_break', 'break_type']
    readonly_fields = ['created_at']
    ordering = ['day', 'start_time']
    
    fieldsets = (
        ('Time Information', {
            'fields': ('day', 'start_time', 'end_time', 'period_number')
        }),
        ('Break Information', {
            'fields': ('is_break', 'break_type')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_duration(self, obj):
        from datetime import datetime
        start = datetime.combine(datetime.today(), obj.start_time)
        end = datetime.combine(datetime.today(), obj.end_time)
        duration = end - start
        minutes = duration.total_seconds() / 60
        return f"{int(minutes)} minutes"
    get_duration.short_description = 'Duration'


@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = ['class_obj', 'subject', 'teacher', 'room', 'time_slot', 'is_active', 'get_conflicts']
    list_filter = ['is_active', 'time_slot__day', 'subject', 'teacher', 'room']
    search_fields = ['class_obj__name', 'subject__name', 'teacher__user__first_name', 'teacher__user__last_name', 'room__name']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['class_obj', 'subject', 'teacher', 'room', 'time_slot']
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('class_obj', 'subject', 'teacher', 'room', 'time_slot')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_conflicts(self, obj):
        conflicts = []
        
        # Check teacher conflicts
        teacher_conflicts = ClassSchedule.objects.filter(
            teacher=obj.teacher,
            time_slot=obj.time_slot,
            is_active=True
        ).exclude(id=obj.id)
        
        if teacher_conflicts.exists():
            conflicts.append('Teacher conflict')
        
        # Check room conflicts
        room_conflicts = ClassSchedule.objects.filter(
            room=obj.room,
            time_slot=obj.time_slot,
            is_active=True
        ).exclude(id=obj.id)
        
        if room_conflicts.exists():
            conflicts.append('Room conflict')
        
        if conflicts:
            return format_html('<span class="badge bg-danger">{}</span>', ', '.join(conflicts))
        return format_html('<span class="badge bg-success">No conflicts</span>')
    get_conflicts.short_description = 'Conflicts'
    
    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()
            super().save_model(request, obj, form, change)
        except Exception as e:
            self.message_user(request, f"Error saving schedule: {str(e)}", level='ERROR')


@admin.register(TeacherSchedule)
class TeacherScheduleAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'time_slot', 'is_available', 'reason', 'created_at']
    list_filter = ['is_available', 'time_slot__day']
    search_fields = ['teacher__user__first_name', 'teacher__user__last_name', 'reason']
    list_editable = ['is_available']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['teacher', 'time_slot']
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('teacher', 'time_slot')
        }),
        ('Availability', {
            'fields': ('is_available', 'reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RoomSchedule)
class RoomScheduleAdmin(admin.ModelAdmin):
    list_display = ['room', 'time_slot', 'is_available', 'reason', 'created_at']
    list_filter = ['is_available', 'time_slot__day', 'room__room_type']
    search_fields = ['room__name', 'reason']
    list_editable = ['is_available']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['room', 'time_slot']
    
    fieldsets = (
        ('Schedule Information', {
            'fields': ('room', 'time_slot')
        }),
        ('Availability', {
            'fields': ('is_available', 'reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AcademicCalendar)
class AcademicCalendarAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'start_date', 'end_date', 'is_all_day', 'is_school_holiday', 'duration_days']
    list_filter = ['event_type', 'is_all_day', 'is_school_holiday', 'is_recurring', 'start_date']
    search_fields = ['title', 'description']
    list_editable = ['is_all_day', 'is_school_holiday']
    readonly_fields = ['created_at', 'updated_at', 'duration_days']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'event_type', 'description')
        }),
        ('Date & Time', {
            'fields': ('start_date', 'end_date', 'start_time', 'end_time', 'is_all_day')
        }),
        ('Event Settings', {
            'fields': ('is_school_holiday', 'is_recurring', 'recurrence_pattern')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'duration_days'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_holiday', 'mark_as_event', 'duplicate_event']
    
    def mark_as_holiday(self, request, queryset):
        updated = queryset.update(is_school_holiday=True, event_type='holiday')
        self.message_user(request, f'{updated} events marked as school holidays.')
    mark_as_holiday.short_description = "Mark selected events as school holidays"
    
    def mark_as_event(self, request, queryset):
        updated = queryset.update(event_type='event')
        self.message_user(request, f'{updated} events updated.')
    mark_as_event.short_description = "Mark selected events as general events"
    
    def duplicate_event(self, request, queryset):
        for event in queryset:
            event.pk = None
            event.title = f"Copy of {event.title}"
            event.save()
        self.message_user(request, f'{queryset.count()} events duplicated.')
    duplicate_event.short_description = "Duplicate selected events"


# Custom admin site configuration
admin.site.site_header = "ADOM Institute - Timetable"
admin.site.site_title = "ADOM Institute Timetable"
admin.site.index_title = "Welcome to Timetable Management"
