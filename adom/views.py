from django.conf import settings
from django.http import HttpResponse, JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok", "service": "adom-institute"})


def robots_txt(request):
    """Serve /robots.txt.

    The public marketing pages are crawlable; every authenticated application
    area, the API and the interactive search endpoint are disallowed so they
    never enter the index.
    """
    disallow = [
        '/admin/',
        '/api/',
        '/accounts/',
        '/students/',
        '/teachers/',
        '/academics/',
        '/fees/',
        '/attendance/',
        '/communication/',
        '/timetable/',
        '/library/',
        '/analytics/',
        '/adom-institute/',
        '/swagger/',
        '/redoc/',
        '/search/',
    ]
    lines = ['User-agent: *', 'Allow: /']
    lines += [f'Disallow: {path}' for path in disallow]
    lines += ['', f'Sitemap: {settings.SITE_BASE_URL}/sitemap.xml', '']
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
