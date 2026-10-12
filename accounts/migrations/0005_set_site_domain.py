from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def set_site_domain(apps, schema_editor):
    """Point the current Site at the canonical public origin.

    ``django.contrib.sitemaps`` builds absolute URLs from the Site record, so
    keeping it aligned with ``settings.SITE_BASE_URL`` makes the sitemap emit
    https://adominstitute.com URLs instead of the ``example.com`` default.
    """
    Site = apps.get_model('sites', 'Site')
    domain = urlparse(settings.SITE_BASE_URL).netloc
    if not domain:
        return
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={'domain': domain, 'name': settings.SITE_NAME},
    )


def unset_site_domain(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    Site.objects.filter(id=settings.SITE_ID).update(
        domain='example.com',
        name='example.com',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_profile_picture'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(set_site_domain, unset_site_domain),
    ]
