# Third-party
from django.conf import settings
from django.core.paginator import InvalidPage, Paginator
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination, _positive_int
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class CustomPageNumberPagination(PageNumberPagination):
    """This Pagination class allows a request to pass the page_size query param
    for usual pagination functionality but adds custom whereby a value of
    page_size=0 will return all items
    """

    page_size_query_param = "page_size"

    def paginate_queryset(self, queryset, request, view=None):
        """Override to check for page_size=0 if so then return all items else
        execute original parent functionality
        """
        page_size = self.get_page_size(request)

        if not self._page_size_is_all(page_size):
            return super().paginate_queryset(queryset, request, view)

        paginator = self.django_paginator_class(queryset, queryset.count() or 1)
        self.page = paginator.page(1)

        return list(self.page)

    def get_page_size(self, request):
        """Override to set strict=False to allow a 0 value"""
        if self.page_size_query_param:
            try:
                return _positive_int(
                    request.query_params[self.page_size_query_param],
                    strict=False,
                    cutoff=self.max_page_size,
                )
            except (KeyError, ValueError):
                pass

        return self.page_size

    def _page_size_is_all(self, page_size):
        """If page_size is specified as 0 we use that to mean return all"""
        return page_size == 0


class DashboardPaginator(CustomPageNumberPagination):
    """Custom paginator for dashboards that allows for a page_size of 0 to return all items."""

    def get_next_link(self):
        return (
            f"{settings.DASHBOARD_SERVICE_URL}?page={self.page.next_page_number()}"
            if self.page.has_next()
            else None
        )

    def get_previous_link(self):
        return (
            f"{settings.DASHBOARD_SERVICE_URL}?page={self.page.previous_page_number()}"
            if self.page.has_previous()
            else None
        )

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "current_page": self.page.number,
                "page_numbers": self.page.paginator.get_elided_page_range(
                    self.page.number, on_each_side=1, on_ends=1
                ),
                "results": data,
            }
        )


class Auth0Paginator(Paginator):
    def __init__(self, object_list, per_page, total_count=25, **kwargs):
        self.total_count = total_count
        super().__init__(object_list, per_page, **kwargs)

    @property
    def count(self):
        """Return the total number of objects, across all pages."""
        return self.total_count


class Auth0ApiPagination(Auth0Paginator):

    def __init__(self, request, page_number, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        self._page = self.get_page(page_number)

    def get_page_url(self, page_number):
        url = self.request.build_absolute_uri()
        return replace_query_param(url, "page", page_number)

    def get_next_link(self):
        if not self._page.has_next():
            return None
        return self.get_page_url(self._page.next_page_number())

    def get_previous_link(self):
        if not self._page.has_previous():
            return None
        return self.get_page_url(self._page.previous_page_number())

    def get_paginated_response(self):
        return Response(
            {
                "count": self.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": self.object_list,
            }
        )
