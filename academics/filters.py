from django.db.models import F
from django_filters import rest_framework as filters

from .models import StudentAssignment


class StudentAssignmentFilter(filters.FilterSet):
    """Filters for StudentAssignment.

    `is_late` and `is_graded` are Python properties on the model, not database
    columns, so they cannot be listed in `filterset_fields` -- doing so makes
    django-filter raise
    `TypeError: 'Meta.fields' must not contain non-model field names` and turns
    every request to this endpoint into an HTTP 500. They are expressed here as
    method filters that translate the property definitions into SQL:

        is_late   -> submitted_at > assignment.due_date
        is_graded -> marks_obtained IS NOT NULL
    """

    is_late = filters.BooleanFilter(method="filter_is_late")
    is_graded = filters.BooleanFilter(method="filter_is_graded")

    class Meta:
        model = StudentAssignment
        fields = ['assignment']

    def filter_is_late(self, queryset, name, value):
        lookup = "submitted_at__gt" if value else "submitted_at__lte"
        return queryset.filter(**{lookup: F("assignment__due_date")}).distinct()

    def filter_is_graded(self, queryset, name, value):
        return queryset.filter(marks_obtained__isnull=not value).distinct()
