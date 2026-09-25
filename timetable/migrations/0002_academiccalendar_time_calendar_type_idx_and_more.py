from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        ('teachers', '0001_initial'),
        ('timetable', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex('academiccalendar', models.Index(fields=['event_type', 'start_date'], name='time_calendar_type_idx')),
        migrations.AddIndex('classschedule', models.Index(fields=['teacher', 'time_slot', 'is_active'], name='time_sched_teacher_idx')),
        migrations.AddIndex('classschedule', models.Index(fields=['room', 'time_slot', 'is_active'], name='time_sched_room_idx')),
        migrations.AddIndex('room', models.Index(fields=['room_type', 'is_active'], name='time_room_type_idx')),
        migrations.AddIndex('timeslot', models.Index(fields=['day', 'start_time'], name='time_slot_day_idx')),
        migrations.AddConstraint(
            'academiccalendar',
            models.CheckConstraint(check=models.Q(end_date__gte=models.F('start_date')), name='time_calendar_dates_ck'),
        ),
        migrations.AddConstraint('room', models.CheckConstraint(check=models.Q(capacity__gt=0), name='time_room_capacity_ck')),
        migrations.AddConstraint(
            'timeslot',
            models.CheckConstraint(check=models.Q(end_time__gt=models.F('start_time')), name='time_slot_range_ck'),
        ),
    ]
