"""Sitemaps for the public marketing site.

Only crawlable, indexable pages belong here. Authenticated application areas
(dashboards, APIs, admin) are intentionally excluded and are also blocked in
robots.txt via ``adom.views.robots_txt``.

When blog/article models are added, register an additional ``Sitemap`` subclass
(e.g. ``ArticleSitemap``) and add it to the ``sitemaps`` mapping in
``adom.urls``; the framework will serve both through one sitemap index.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicStaticSitemap(Sitemap):
    """Named public URL patterns with sensible crawl priorities."""

    protocol = 'https'

    # (url name, priority, changefreq)
    _PAGES = [
        ('home', 1.0, 'weekly'),
        ('public_courses', 0.9, 'weekly'),
        ('public_admissions', 0.9, 'monthly'),
        ('public_tuition', 0.8, 'monthly'),
        ('public_books', 0.8, 'weekly'),
        ('public_ict', 0.8, 'weekly'),
        ('public_school_solutions', 0.8, 'monthly'),
        ('public_shop', 0.7, 'weekly'),
        ('public_about', 0.6, 'yearly'),
        ('public_contact', 0.6, 'yearly'),
        ('public_privacy', 0.3, 'yearly'),
        ('public_terms', 0.3, 'yearly'),
    ]

    def items(self):
        return [name for name, _priority, _changefreq in self._PAGES]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return next(priority for name, priority, _ in self._PAGES if name == item)

    def changefreq(self, item):
        return next(freq for name, _, freq in self._PAGES if name == item)
