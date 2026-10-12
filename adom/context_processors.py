from django.conf import settings


def seo(request):
    """Site-wide SEO defaults available to every template.

    Per-page overrides are passed through the ``seo/meta.html`` include, which
    falls back to these values when a page does not specify its own.
    """
    return {
        'site_name': settings.SITE_NAME,
        'site_base_url': settings.SITE_BASE_URL,
        'site_default_description': settings.SITE_DESCRIPTION,
        'google_site_verification': settings.GOOGLE_SITE_VERIFICATION,
    }
