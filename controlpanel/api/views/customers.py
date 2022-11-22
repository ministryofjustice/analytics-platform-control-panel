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
from rest_framework.pagination import PageNumberPagination
from controlpanel.api.pagination import Auth0Pagination

class AppGroupIdApiView(GenericAPIView):
    queryset = App.objects.all()
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    def get(self, request, *args, pk=None, **kwargs):
        app = App.objects.get(pk=pk)
        return Response(dict(group_id=app.get_group_id()))


class AppCustomersPageAPIView(GenericAPIView):
    queryset = App.objects.all()
    serializer_class = serializers.AppCustomerSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"
    pagination_class = Auth0Pagination

    def get(self, request, *args, pk=None, **kwargs):
        app = App.objects.get(pk=pk)

        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 25)
        group_id = request.GET.get('group_id')

        customers = app.customer_paginated(page, group_id=group_id, per_page=per_page)
        if not customers:
            return Response([])

        total_count = customers.get('total', 0)
        customer_result = customers.get('users', [])
        paginator = self.pagination_class().add_total(total_count)
        paginator.page_size = per_page

        paginator.paginate_queryset(queryset=customer_result, request=request)

        serializer = self.get_serializer(data=customer_result, many=True)
        serializer.is_valid(raise_exception=True)

        return paginator.get_paginated_response(serializer.data)


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
