from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_tuitionenquiry'),
    ]

    operations = [
        migrations.AddField(
            model_name='tuitionenquiry',
            name='current_school',
            field=models.CharField(default='Not provided', max_length=180),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='tuitionenquiry',
            name='learning_level',
            field=models.CharField(
                choices=[
                    ('day_care', 'Day Care (0–3 years)'),
                    ('nursery', 'Nursery (3–4 years)'),
                    ('pre_school', 'Pre-school (4–5 years)'),
                    ('primary_1', 'Primary Grade 1'),
                    ('primary_2', 'Primary Grade 2'),
                    ('primary_3', 'Primary Grade 3'),
                    ('primary_4', 'Primary Grade 4'),
                    ('primary_5', 'Primary Grade 5'),
                    ('primary_6', 'Primary Grade 6'),
                    ('form_1', 'Secondary Form 1'),
                    ('form_2', 'Secondary Form 2'),
                    ('form_3', 'Secondary Form 3'),
                    ('form_4', 'Secondary Form 4'),
                    ('form_5', 'Secondary Form 5'),
                    ('advanced_level', 'Advanced Level'),
                ],
                max_length=20,
            ),
        ),
    ]
