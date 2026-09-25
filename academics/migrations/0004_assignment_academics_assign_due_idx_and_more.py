from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0003_alter_assignment_attachment_and_more'),
        ('students', '0004_academicyear_students_year_inst_idx_and_more'),
        ('teachers', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex('assignment', models.Index(fields=['class_obj', 'due_date'], name='academics_assign_due_idx')),
        migrations.AddIndex('exam', models.Index(fields=['academic_year', 'class_obj', 'is_active'], name='academics_exam_scope_idx')),
        migrations.AddIndex('examsubject', models.Index(fields=['exam', 'subject', 'exam_date'], name='academics_exsub_date_idx')),
        migrations.AddIndex('studentassignment', models.Index(fields=['student', 'assignment'], name='academics_sub_student_idx')),
        migrations.AddConstraint(
            'assignment',
            models.CheckConstraint(check=models.Q(max_marks__gt=0), name='academics_assign_marks_ck'),
        ),
        migrations.AddConstraint(
            'exam',
            models.CheckConstraint(check=models.Q(end_date__gte=models.F('start_date')), name='academics_exam_dates_ck'),
        ),
        migrations.AddConstraint(
            'exam',
            models.CheckConstraint(check=models.Q(passing_marks__lte=models.F('total_marks')), name='academics_exam_pass_ck'),
        ),
        migrations.AddConstraint(
            'examsubject',
            models.CheckConstraint(check=models.Q(passing_marks__lte=models.F('max_marks')), name='academics_exsub_pass_ck'),
        ),
        migrations.AddConstraint(
            'studentassignment',
            models.CheckConstraint(
                check=models.Q(marks_obtained__isnull=True) | models.Q(marks_obtained__gte=0),
                name='academics_submission_ck',
            ),
        ),
        migrations.AddConstraint(
            'studentexamresult',
            models.CheckConstraint(check=models.Q(marks_obtained__gte=0), name='academics_result_marks_ck'),
        ),
    ]
