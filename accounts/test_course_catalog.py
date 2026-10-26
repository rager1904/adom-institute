from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .course_catalog import COURSES


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class PublicCourseTests(SimpleTestCase):
    def test_catalogue_is_paginated_with_course_links(self):
        response = self.client.get(reverse('public_courses'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 6)
        self.assertContains(response, reverse('public_course_detail', args=['ai-chatgpt-for-beginners']))
        self.assertContains(response, 'More courses')

    def test_category_and_search_work_together(self):
        response = self.client.get(reverse('public_courses'), {'category': 'ict', 'q': 'computer'})
        self.assertTrue(response.context['page_obj'].paginator.count)
        for course in response.context['page_obj']:
            self.assertEqual(course['category'], 'ict')
            self.assertIn('computer', f"{course['title']} {course['category_label']} {course['summary']}".lower())

    def test_empty_state_escapes_user_search(self):
        response = self.client.get(reverse('public_courses'), {'q': '<script>alert(1)</script>'})
        self.assertContains(response, 'No courses found')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_every_course_has_a_unique_working_detail_route(self):
        self.assertEqual(len(COURSES), len({course['slug'] for course in COURSES}))
        for course in COURSES:
            with self.subTest(slug=course['slug']):
                response = self.client.get(reverse('public_course_detail', args=[course['slug']]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Enrol for this course')
                self.assertContains(response, 'https://wa.me/260967920605?text=')

    def test_unknown_course_returns_404(self):
        self.assertEqual(self.client.get(reverse('public_course_detail', args=['unknown-course'])).status_code, 404)

    def test_unconfirmed_prices_are_not_invented(self):
        response = self.client.get(reverse('public_course_detail', args=['practical-bookkeeping']))
        self.assertContains(response, 'Enquire for details')
        self.assertNotContains(response, 'K750')
