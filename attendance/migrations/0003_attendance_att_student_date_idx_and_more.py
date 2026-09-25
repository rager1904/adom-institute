from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_alter_leaverequest_supporting_document'),
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        ('teachers', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex('attendance', models.Index(fields=['student', 'date', 'status'], name='att_student_date_idx')),
        migrations.AddIndex('classattendance', models.Index(fields=['class_obj', 'date'], name='att_class_date_idx')),
        migrations.AddIndex('leaverequest', models.Index(fields=['status', 'start_date'], name='att_leave_status_idx')),
        migrations.AddIndex('teacherattendance', models.Index(fields=['teacher', 'date', 'status'], name='att_teacher_date_idx')),
        migrations.AddConstraint('classattendance', models.CheckConstraint(check=models.Q(present_count__lte=models.F('total_students')), name='att_class_present_ck')),
        migrations.AddConstraint('classattendance', models.CheckConstraint(check=models.Q(absent_count__lte=models.F('total_students')), name='att_class_absent_ck')),
        migrations.AddConstraint('classattendance', models.CheckConstraint(check=models.Q(late_count__lte=models.F('total_students')), name='att_class_late_ck')),
        migrations.AddConstraint('leaverequest', models.CheckConstraint(check=models.Q(end_date__gte=models.F('start_date')), name='att_leave_dates_ck')),
        migrations.AddConstraint(
            'leaverequest',
            models.CheckConstraint(
                check=(
                    models.Q(student__isnull=False, teacher__isnull=True)
                    | models.Q(student__isnull=True, teacher__isnull=False)
                ),
                name='att_leave_one_owner_ck',
            ),
        ),
    ]
