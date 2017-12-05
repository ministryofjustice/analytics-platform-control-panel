from rest_framework.pagination import PageNumberPagination, _positive_int


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
        if page_size != 0:
            return super().paginate_queryset(queryset, request, view)

        paginator = self.django_paginator_class(queryset, queryset.count())
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
