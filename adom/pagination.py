"""Shared DRF pagination for ADOM Institute API views."""
from rest_framework.pagination import PageNumberPagination


class DefaultOrderedPagination(PageNumberPagination):
    """PageNumberPagination that guarantees a deterministic row order.

    Several querysets in this project (e.g. ``accounts.User``,
    ``academics.StudentExamResult``, ``fees.StudentFee``) have no ``Meta.ordering``
    and are returned unsorted. Paginating an unordered queryset makes
    ``LIMIT``/``OFFSET`` return rows in whatever order the database happens to
    produce, so a client walking pages can see the same row twice and silently
    miss others. DRF only emits an ``UnorderedObjectListWarning`` for this.

    Ordering by primary key is unique and stable, and it matches the primary-key
    index, so it does not add a sort to queries that were already index-ordered.
    An explicit ``?ordering=`` from OrderingFilter is applied upstream in
    ``filter_queryset``, so it is preserved here.
    """

    def paginate_queryset(self, queryset, request, view=None):
        if not queryset.ordered:
            queryset = queryset.order_by(queryset.model._meta.pk.name)
        return super().paginate_queryset(queryset, request, view)
