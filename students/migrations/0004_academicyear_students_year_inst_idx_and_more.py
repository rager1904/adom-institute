from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_profile_picture'),
        ('students', '0003_backfill_default_institution'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex('academicyear', models.Index(fields=['institution', 'is_active'], name='students_year_inst_idx')),
        migrations.AddIndex('class', models.Index(fields=['academic_year', 'is_active'], name='students_class_year_idx')),
        migrations.AddIndex('parent', models.Index(fields=['student', 'is_primary_contact'], name='students_parent_primary_idx')),
        migrations.AddIndex('parent', models.Index(fields=['student', 'is_emergency_contact'], name='students_parent_emerg_idx')),
        migrations.AddIndex('student', models.Index(fields=['current_class', 'is_active'], name='students_class_active_idx')),
        migrations.AddIndex('student', models.Index(fields=['admission_status', 'is_active'], name='students_adm_status_idx')),
        migrations.AddConstraint(
            'academicyear',
            models.CheckConstraint(check=models.Q(end_date__gt=models.F('start_date')), name='students_year_dates_ck'),
        ),
        migrations.AddConstraint(
            'class',
            models.CheckConstraint(check=models.Q(capacity__gt=0), name='students_class_cap_ck'),
        ),
        migrations.AddConstraint(
            'student',
            models.CheckConstraint(check=models.Q(admission_date__gte=models.F('date_of_birth')), name='students_admission_age_ck'),
        ),
    ]
