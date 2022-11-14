import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django.http.response import Http404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import get_error_detail
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from controlpanel.api import permissions, serializers
from controlpanel.api.models import App
from django.contrib.auth.models import Permission
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination
from rest_framework.utils.urls import remove_query_param, replace_query_param


class CustomPagination(PageNumberPagination):
    # def get_paginated_response(self, data):
    #     return Response({
    #         'links': {
    #             'next': self.get_next_link(),
    #             'previous': self.get_previous_link()
    #         },
    #         'count': self.page.paginator.count,
    #         'results': data
    #     })

    def get_next_link(self):
        if (self.offset * self.limit) >= self.count:
            return None

        url = self.request.build_absolute_uri()
        url = replace_query_param(url, self.limit_query_param, self.limit)
        return url
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)


class AppCustomersPageAPIView(CustomPagination, GenericAPIView):
    queryset = App.objects.all()
    serializer_class = serializers.AppCustomerSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    default_limit = 100
    offset_query_param = "per_page"
    limit_query_param = "page"
    # page_size_query_param = "per_page"
    # page = 1
    # page_query_param = 
    # offset = 2
    # limit = 0

    # def get_paginated_response(self, data):  # pragma: no cover
    #     raise NotImplementedError('get_paginated_response() must be implemented.')

    # def get_next_link(self):
    #     if self.offset + self.limit >= self.count:
    #         print('\n\nnext link >> ', f'offset {self.offset} - limit {self.limit} -- count {self.count}', '\n\n')
    #         print('>>> ', )
    #         return None

    #     url = self.request.build_absolute_uri()
    #     return replace_query_param(url, self.limit_query_param, self.limit)
    

    def get(self, request, *args, pk=None, page=1, per_page=2, **kwargs):
        app = App.objects.get(pk=pk)
        customers = app.customer_paginated(page, per_page=per_page)
        if not customers:
            raise Http404

        print('customers >> ', customers, '\n\n')

        self.offset = page
        self.limit = per_page
        self.count = customers.get('total', 0)
        # len(customers.get('users', []))


        serializer = self.get_serializer(data=customers.get('users', []), many=True)
        serializer.is_valid(raise_exception=True)

        # paginate = self.get_paginated_response(serializer.data)
        print('get_paginated_response >> ', dict(self.get_paginated_response(customers).data), '\n\n')
        print('paginate >> ', self.get_limit(request), '\n\n')
        print('page links >>> ', self.get_next_link())
        return Response(serializer.data)

    # def paginate_queryset(self, queryset, request, view=None):
    #     self.limit = self.get_limit(request)
    #     if self.limit is None:
    #         return None

    #     self.count = self.get_count(queryset)
    #     self.offset = self.get_offset(request)
    #     self.request = request
    #     if self.count > self.limit and self.template is not None:
    #         self.display_page_controls = True

    #     if self.count == 0 or self.offset > self.count:
    #         return []
    #     return list(queryset[self.offset:self.offset + self.limit])



    # def paginate_queryset(self, queryset, request, view=None):
    #     self.page_size = self.get_page_size(request)
    #     if not self.page_size:
    #         return None

    #     self.base_url = request.build_absolute_uri()
    #     self.ordering = self.get_ordering(request, queryset, view)

    #     self.cursor = self.decode_cursor(request)
    #     if self.cursor is None:
    #         (offset, reverse, current_position) = (0, False, None)
    #     else:
    #         (offset, reverse, current_position) = self.cursor

    #     # Cursor pagination always enforces an ordering.
    #     if reverse:
    #         queryset = queryset.order_by(*_reverse_ordering(self.ordering))
    #     else:
    #         queryset = queryset.order_by(*self.ordering)

    #     # If we have a cursor with a fixed position then filter by that.
    #     if current_position is not None:
    #         order = self.ordering[0]
    #         is_reversed = order.startswith('-')
    #         order_attr = order.lstrip('-')

    #         # Test for: (cursor reversed) XOR (queryset reversed)
    #         if self.cursor.reverse != is_reversed:
    #             kwargs = {order_attr + '__lt': current_position}
    #         else:
    #             kwargs = {order_attr + '__gt': current_position}

    #         queryset = queryset.filter(**kwargs)

    #     # If we have an offset cursor then offset the entire page by that amount.
    #     # We also always fetch an extra item in order to determine if there is a
    #     # page following on from this one.
    #     results = list(queryset[offset:offset + self.page_size + 1])
    #     self.page = list(results[:self.page_size])

    #     # Determine the position of the final item following the page.
    #     if len(results) > len(self.page):
    #         has_following_position = True
    #         following_position = self._get_position_from_instance(results[-1], self.ordering)
    #     else:
    #         has_following_position = False
    #         following_position = None

    #     if reverse:
    #         # If we have a reverse queryset, then the query ordering was in reverse
    #         # so we need to reverse the items again before returning them to the user.
    #         self.page = list(reversed(self.page))

    #         # Determine next and previous positions for reverse cursors.
    #         self.has_next = (current_position is not None) or (offset > 0)
    #         self.has_previous = has_following_position
    #         if self.has_next:
    #             self.next_position = current_position
    #         if self.has_previous:
    #             self.previous_position = following_position
    #     else:
    #         # Determine next and previous positions for forward cursors.
    #         self.has_next = has_following_position
    #         self.has_previous = (current_position is not None) or (offset > 0)
    #         if self.has_next:
    #             self.next_position = following_position
    #         if self.has_previous:
    #             self.previous_position = current_position

    #     # Display page controls in the browsable API if there is more
    #     # than one page.
    #     if (self.has_previous or self.has_next) and self.template is not None:
    #         self.display_page_controls = True

    #     return self.page



class AppCustomersAPIView(GenericAPIView):
    queryset = App.objects.all()
    serializer_class = serializers.AppCustomerSerializer
    permission_classes = (permissions.IsSuperuser,)

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        customers = app.customers

        if customers is None:
            raise Http404

        serializer = self.get_serializer(data=customers, many=True)
        serializer.is_valid()

        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        app = self.get_object()

        delimiters = re.compile(r'[,; ]+')
        emails = delimiters.split(serializer.validated_data['email'])

        errors = []
        for email in emails:
            validator = EmailValidator(
                message=f'{email} is not a valid email address')
            try:
                validator(email)
            except DjangoValidationError as error:
                errors.extend(get_error_detail(error))
        if errors:
            raise ValidationError(errors)

        app.add_customers(emails)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AppCustomersDetailAPIView(GenericAPIView):
    queryset = App.objects.all()
    permission_classes = (permissions.IsSuperuser,)

    def delete(self, request, *args, **kwargs):
        app = self.get_object()
        app.delete_customers([kwargs['user_id']])

        return Response(status=status.HTTP_204_NO_CONTENT)
