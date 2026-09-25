from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Room, TimeSlot, ClassSchedule, TeacherSchedule, RoomSchedule, AcademicCalendar


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'room_type', 'capacity', 'building', 'floor', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter room name'}),
            'room_type': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'building': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Building name'}),
            'floor': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Room description'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Room.objects.filter(name=name).exclude(pk=self.instance.pk if self.instance.pk else None).exists():
            raise ValidationError('A room with this name already exists.')
        return name

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity <= 0:
            raise ValidationError('Capacity must be greater than 0.')
        return capacity


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['day', 'start_time', 'end_time', 'period_number', 'is_break', 'break_type']
        widgets = {
            'day': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'period_number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'is_break': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'break_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lunch, Recess, etc.'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        day = cleaned_data.get('day')
        period_number = cleaned_data.get('period_number')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

        if day and start_time and end_time:
            # Check for overlapping time slots on the same day
            overlapping = TimeSlot.objects.filter(
                day=day,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if overlapping.exists():
                raise ValidationError('This time slot overlaps with an existing time slot on the same day.')

        if period_number and period_number <= 0:
            raise ValidationError('Period number must be greater than 0.')

        return cleaned_data


class ClassScheduleForm(forms.ModelForm):
    class Meta:
        model = ClassSchedule
        fields = ['class_obj', 'subject', 'teacher', 'room', 'time_slot', 'is_active']
        widgets = {
            'class_obj': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        class_obj = cleaned_data.get('class_obj')
        subject = cleaned_data.get('subject')
        teacher = cleaned_data.get('teacher')
        room = cleaned_data.get('room')
        time_slot = cleaned_data.get('time_slot')

        if class_obj and time_slot:
            # Check for class conflicts
            class_conflicts = ClassSchedule.objects.filter(
                class_obj=class_obj,
                time_slot=time_slot,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if class_conflicts.exists():
                raise ValidationError('This class already has a subject scheduled at this time.')

        if teacher and time_slot:
            # Check for teacher conflicts
            teacher_conflicts = ClassSchedule.objects.filter(
                teacher=teacher,
                time_slot=time_slot,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if teacher_conflicts.exists():
                raise ValidationError('This teacher is already assigned to another class at this time.')

        if room and time_slot:
            # Check for room conflicts
            room_conflicts = ClassSchedule.objects.filter(
                room=room,
                time_slot=time_slot,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if room_conflicts.exists():
                raise ValidationError('This room is already occupied at this time.')

        return cleaned_data


class TeacherScheduleForm(forms.ModelForm):
    class Meta:
        model = TeacherSchedule
        fields = ['teacher', 'time_slot', 'is_available', 'reason']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for unavailability'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        time_slot = cleaned_data.get('time_slot')

        if teacher and time_slot:
            # Check for existing schedule
            existing = TeacherSchedule.objects.filter(
                teacher=teacher,
                time_slot=time_slot
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if existing.exists():
                raise ValidationError('This teacher already has a schedule for this time slot.')

        return cleaned_data


class RoomScheduleForm(forms.ModelForm):
    class Meta:
        model = RoomSchedule
        fields = ['room', 'time_slot', 'is_available', 'reason']
        widgets = {
            'room': forms.Select(attrs={'class': 'form-select'}),
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for unavailability'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        time_slot = cleaned_data.get('time_slot')

        if room and time_slot:
            # Check for existing schedule
            existing = RoomSchedule.objects.filter(
                room=room,
                time_slot=time_slot
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if existing.exists():
                raise ValidationError('This room already has a schedule for this time slot.')

        return cleaned_data


class AcademicCalendarForm(forms.ModelForm):
    class Meta:
        model = AcademicCalendar
        fields = [
            'title', 'event_type', 'description', 'start_date', 'end_date',
            'start_time', 'end_time', 'is_all_day', 'is_school_holiday',
            'is_recurring', 'recurrence_pattern'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Event title'}),
            'event_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Event description'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'is_all_day': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_school_holiday': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'recurrence_pattern': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Weekly, Monthly, etc.'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        is_all_day = cleaned_data.get('is_all_day')

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('End date must be after or equal to start date.')

        if not is_all_day and start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

        return cleaned_data


# Search and Filter Forms
class RoomSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, building...',
            'class': 'form-control'
        })
    )
    room_type_filter = forms.ChoiceField(
        choices=[('', 'All Types')] + Room.RoomType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class TimeSlotSearchForm(forms.Form):
    day_filter = forms.ChoiceField(
        choices=[('', 'All Days')] + TimeSlot.DayOfWeek.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_break_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Break'), ('False', 'Class')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class ClassScheduleSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by class, subject, teacher...',
            'class': 'form-control'
        })
    )
    day_filter = forms.ChoiceField(
        choices=[('', 'All Days')] + TimeSlot.DayOfWeek.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_active_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class AcademicCalendarSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by title, description...',
            'class': 'form-control'
        })
    )
    event_type_filter = forms.ChoiceField(
        choices=[('', 'All Types')] + AcademicCalendar.EventType.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    is_school_holiday_filter = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Holidays'), ('False', 'Events')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
