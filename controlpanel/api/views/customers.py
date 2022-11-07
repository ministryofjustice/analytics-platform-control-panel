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

class AppCustomersPageAPIView(GenericAPIView):
    queryset = App.objects.all()
    serializer_class = serializers.Auth0ResponseSerializer
    permission_classes = (permissions.AppPermissions,)
    action = "retrieve"

    def get(self, request, *args, pk=None, page=1, **kwargs):
        app = App.objects.get(pk=pk)
        customers = app.customer_paginated(page)
        if not customers:
            raise Http404

        serializer = self.get_serializer(data=customers)
        serializer.is_valid()
        return Response(serializer.data)


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
