from rest_framework.pagination import PageNumberPagination, _positive_int
from django.core.paginator import Paginator
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param

class CustomPageNumberPagination(PageNumberPagination):
    """This Pagination class allows a request to pass the page_size query param
    for usual pagination functionality but adds custom whereby a value of
    page_size=0 will return all items
    """
    page_size_query_param = 'page_size'

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
        """Override to set strict=False to allow a 0 value
        """
        if self.page_size_query_param:
            try:
                return _positive_int(
                    request.query_params[self.page_size_query_param],
                    strict=False,
                    cutoff=self.max_page_size
                )
            except (KeyError, ValueError):
                pass

        return self.page_size

    def _page_size_is_all(self, page_size):
        """If page_size is specified as 0 we use that to mean return all
        """
        return page_size == 0


class Auth0Paginator(Paginator):
    @property
    def count(self):
        """Return the total number of objects."""
        return self.total_count


class Auth0Pagination(PageNumberPagination):
    django_paginator_class = Auth0Paginator
    page_size_query_param = "per_page"
    page_query_param = 'page'

    def add_total(self, total_count: int):
        setattr(self.django_paginator_class, 'total_count', total_count)
        return self

    def get_paginated_response(self, data, *args, total_count=0, **kwargs):
        return Response(
            dict(
                count = total_count,
                links = dict(
                    next = self.get_next_link(),
                    previous = self.get_previous_link()
                ),
                results = data
            ))

    def get_next_link(self):
        url = super().get_next_link()
        page_size  = self.get_page_size(self.request)
        url = replace_query_param(url, self.page_size_query_param, page_size)
        return url