from rest_framework import serializers

from .models import Room, TimeSlot, ClassSchedule


class RoomSerializer(serializers.ModelSerializer):
    schedule_count = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_schedule_count(self, obj):
        return obj.schedules.count()

    def validate_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Capacity must be greater than zero.')
        return value


class TimeSlotSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = TimeSlot
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_label(self, obj):
        return f'{obj.get_day_display()} {obj.start_time}-{obj.end_time}'

    def validate(self, data):
        start = data.get('start_time', getattr(self.instance, 'start_time', None))
        end = data.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                'The slot must end after it starts.'
            )
        return data


class ClassScheduleSerializer(serializers.ModelSerializer):
    class_details = serializers.SerializerMethodField()
    subject_details = serializers.SerializerMethodField()
    teacher_details = serializers.SerializerMethodField()
    room_details = serializers.SerializerMethodField()
    time_slot_details = serializers.SerializerMethodField()

    class Meta:
        model = ClassSchedule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_class_details(self, obj):
        return {'id': obj.class_obj_id, 'name': obj.class_obj.name}

    def get_subject_details(self, obj):
        return {'id': obj.subject_id, 'name': obj.subject.name, 'code': obj.subject.code}

    def get_teacher_details(self, obj):
        return {
            'id': obj.teacher_id,
            'employee_id': obj.teacher.employee_id,
            'full_name': obj.teacher.user.get_full_name(),
        }

    def get_room_details(self, obj):
        return {'id': obj.room_id, 'name': obj.room.name}

    def get_time_slot_details(self, obj):
        return {
            'id': obj.time_slot_id,
            'day': obj.time_slot.get_day_display(),
            'start_time': obj.time_slot.start_time,
            'end_time': obj.time_slot.end_time,
        }

    def validate(self, data):
        class_obj = data.get('class_obj', getattr(self.instance, 'class_obj', None))
        time_slot = data.get('time_slot', getattr(self.instance, 'time_slot', None))
        if class_obj and time_slot:
            existing = ClassSchedule.objects.filter(class_obj=class_obj, time_slot=time_slot)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    'That class already has a schedule in this time slot.'
                )
        return data
