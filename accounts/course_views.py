from urllib.parse import urlencode

from django.http import Http404
from django.core.paginator import Paginator
from django.views.generic import TemplateView

from .course_catalog import CATEGORIES, COURSES, COURSES_BY_SLUG


class PublicCourseListView(TemplateView):
    template_name = 'public/courses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()[:100]
        category = self.request.GET.get('category', '')
        if category not in dict(CATEGORIES):
            category = ''
        courses = [item for item in COURSES if (
            (not category or item['category'] == category)
            and (not query or query.casefold() in f"{item['title']} {item['summary']}".casefold())
        )]
        context.update(
            categories=CATEGORIES, selected_category=category, query=query,
            page_obj=Paginator(courses, 6).get_page(self.request.GET.get('page')),
            filter_query=urlencode({'q': query, 'category': category}),
        )
        return context


class PublicCourseDetailView(TemplateView):
    template_name = 'public/course_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = COURSES_BY_SLUG.get(self.kwargs['slug'])
        if course is None:
            raise Http404('Course not found')
        context['course'] = course
        context['enrol_url'] = 'https://wa.me/260967920605?' + urlencode({
            'text': f"Hello ADOM Institute, I would like to enrol for {course['title']}. Please confirm the next intake, schedule and fees."
        })
        context['question_url'] = 'https://wa.me/260967920605?' + urlencode({
            'text': f"Hello ADOM Institute, I have a question about {course['title']}."
        })
        return context
