from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_alter_report_file_path'),
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        ('teachers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex('analyticsevent', models.Index(fields=['user', 'event_type', 'created_at'], name='analytics_event_user_idx')),
        migrations.AddIndex('analyticsevent', models.Index(fields=['event_type', 'created_at'], name='analytics_event_type_idx')),
        migrations.AddIndex('classperformance', models.Index(fields=['academic_year', 'average_percentage'], name='analytics_class_year_idx')),
        migrations.AddIndex('report', models.Index(fields=['report_type', 'generated_at'], name='analytics_report_type_idx')),
        migrations.AddIndex('report', models.Index(fields=['generated_by', 'generated_at'], name='analytics_report_user_idx')),
        migrations.AddIndex('studentperformance', models.Index(fields=['academic_year', 'class_obj', 'percentage'], name='analytics_st_rank_idx')),
        migrations.AddIndex('studentperformance', models.Index(fields=['student', 'academic_year'], name='analytics_st_student_idx')),
        migrations.AddIndex('teacherperformance', models.Index(fields=['academic_year', 'average_student_performance'], name='analytics_teacher_year_idx')),
        migrations.AddConstraint(
            'classperformance',
            models.CheckConstraint(check=models.Q(lowest_percentage__lte=models.F('highest_percentage')), name='analytics_class_range_ck'),
        ),
        migrations.AddConstraint(
            'classperformance',
            models.CheckConstraint(check=models.Q(total_fees_collected__lte=models.F('total_fees_expected')), name='analytics_class_fees_ck'),
        ),
        migrations.AddConstraint(
            'report',
            models.CheckConstraint(
                check=models.Q(generation_time__isnull=True) | models.Q(generation_time__gte=0),
                name='analytics_report_time_ck',
            ),
        ),
        migrations.AddConstraint(
            'schoolanalytics',
            models.CheckConstraint(check=models.Q(total_fees_collected__lte=models.F('total_fees_expected')), name='analytics_school_fees_ck'),
        ),
        migrations.AddConstraint(
            'schoolanalytics',
            models.CheckConstraint(check=models.Q(outstanding_fees__gte=0), name='analytics_school_out_ck'),
        ),
        migrations.AddConstraint(
            'studentperformance',
            models.CheckConstraint(check=models.Q(obtained_marks__lte=models.F('total_marks')), name='analytics_st_marks_ck'),
        ),
        migrations.AddConstraint(
            'studentperformance',
            models.CheckConstraint(check=models.Q(present_days__lte=models.F('total_days')), name='analytics_st_att_ck'),
        ),
        migrations.AddConstraint(
            'studentperformance',
            models.CheckConstraint(check=models.Q(submitted_assignments__lte=models.F('total_assignments')), name='analytics_st_assign_ck'),
        ),
        migrations.AddConstraint(
            'studentperformance',
            models.CheckConstraint(check=models.Q(paid_fees__lte=models.F('total_fees')), name='analytics_st_fees_ck'),
        ),
        migrations.AddConstraint(
            'teacherperformance',
            models.CheckConstraint(check=models.Q(present_days__lte=models.F('total_teaching_days')), name='analytics_teacher_att_ck'),
        ),
        migrations.AddConstraint(
            'teacherperformance',
            models.CheckConstraint(check=models.Q(assignments_graded__lte=models.F('assignments_created')), name='analytics_teacher_assign_ck'),
        ),
    ]
