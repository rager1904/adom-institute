from django.db import models
from django.utils.translation import gettext_lazy as _
from students.models import Class
from teachers.models import Teacher, Subject


class Room(models.Model):
    class RoomType(models.TextChoices):
        CLASSROOM = 'classroom', _('Classroom')
        LABORATORY = 'laboratory', _('Laboratory')
        LIBRARY = 'library', _('Library')
        AUDITORIUM = 'auditorium', _('Auditorium')
        SPORTS = 'sports', _('Sports')
        OFFICE = 'office', _('Office')
        OTHER = 'other', _('Other')
    
    name = models.CharField(max_length=100, unique=True)
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.CLASSROOM)
    capacity = models.PositiveIntegerField(default=30)
    building = models.CharField(max_length=100, blank=True, null=True)
    floor = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable_room'
        constraints = [
            models.CheckConstraint(
                check=models.Q(capacity__gt=0),
                name='time_room_capacity_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['room_type', 'is_active'], name='time_room_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"


class TimeSlot(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = 'monday', _('Monday')
        TUESDAY = 'tuesday', _('Tuesday')
        WEDNESDAY = 'wednesday', _('Wednesday')
        THURSDAY = 'thursday', _('Thursday')
        FRIDAY = 'friday', _('Friday')
        SATURDAY = 'saturday', _('Saturday')
        SUNDAY = 'sunday', _('Sunday')
    
    day = models.CharField(max_length=10, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    period_number = models.PositiveIntegerField()
    
    is_break = models.BooleanField(default=False)
    break_type = models.CharField(max_length=50, blank=True, null=True, help_text='Lunch, Recess, etc.')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'timetable_time_slot'
        unique_together = ('day', 'start_time', 'end_time')
        ordering = ['day', 'start_time']
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_time__gt=models.F('start_time')),
                name='time_slot_range_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['day', 'start_time'], name='time_slot_day_idx'),
        ]
    
    def __str__(self):
        return f"{self.get_day_display()} - {self.start_time} to {self.end_time}"


class ClassSchedule(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schedules')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schedules')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='schedules')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='schedules')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='schedules')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable_class_schedule'
        unique_together = ('class_obj', 'time_slot')
        ordering = ['time_slot__day', 'time_slot__start_time']
        indexes = [
            models.Index(fields=['teacher', 'time_slot', 'is_active'], name='time_sched_teacher_idx'),
            models.Index(fields=['room', 'time_slot', 'is_active'], name='time_sched_room_idx'),
        ]
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.subject.name} ({self.time_slot})"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Check for teacher conflicts
        teacher_conflicts = ClassSchedule.objects.filter(
            teacher=self.teacher,
            time_slot=self.time_slot,
            is_active=True
        ).exclude(id=self.id)
        
        if teacher_conflicts.exists():
            raise ValidationError('Teacher is already assigned to another class at this time.')
        
        # Check for room conflicts
        room_conflicts = ClassSchedule.objects.filter(
            room=self.room,
            time_slot=self.time_slot,
            is_active=True
        ).exclude(id=self.id)
        
        if room_conflicts.exists():
            raise ValidationError('Room is already occupied at this time.')
        
        # Check for class conflicts
        class_conflicts = ClassSchedule.objects.filter(
            class_obj=self.class_obj,
            time_slot=self.time_slot,
            is_active=True
        ).exclude(id=self.id)
        
        if class_conflicts.exists():
            raise ValidationError('Class already has a subject scheduled at this time.')


class TeacherSchedule(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teacher_schedules')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='teacher_schedules')
    
    is_available = models.BooleanField(default=True)
    reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable_teacher_schedule'
        unique_together = ('teacher', 'time_slot')
        ordering = ['time_slot__day', 'time_slot__start_time']
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.time_slot}"


class RoomSchedule(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='room_schedules')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='room_schedules')
    
    is_available = models.BooleanField(default=True)
    reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable_room_schedule'
        unique_together = ('room', 'time_slot')
        ordering = ['time_slot__day', 'time_slot__start_time']
    
    def __str__(self):
        return f"{self.room.name} - {self.time_slot}"


class AcademicCalendar(models.Model):
    class EventType(models.TextChoices):
        HOLIDAY = 'holiday', _('Holiday')
        EXAM = 'exam', _('Exam')
        EVENT = 'event', _('Event')
        MEETING = 'meeting', _('Meeting')
        SPORTS = 'sports', _('Sports')
        CULTURAL = 'cultural', _('Cultural')
        OTHER = 'other', _('Other')
    
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    description = models.TextField(blank=True, null=True)
    
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    
    # Target audience
    is_all_day = models.BooleanField(default=True)
    is_school_holiday = models.BooleanField(default=False)
    
    # Recurring events
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable_academic_calendar'
        ordering = ['start_date', 'start_time']
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='time_calendar_dates_ck',
            ),
        ]
        indexes = [
            models.Index(fields=['event_type', 'start_date'], name='time_calendar_type_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.start_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
