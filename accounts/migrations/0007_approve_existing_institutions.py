from django.db import migrations


def approve_existing_institutions(apps, schema_editor):
    Institution = apps.get_model('accounts', 'Institution')
    Institution.objects.exclude(status='approved').update(status='approved')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_institution_approved_at_institution_approved_by_and_more'),
    ]

    operations = [
        migrations.RunPython(approve_existing_institutions, noop),
    ]
