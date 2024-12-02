# Standard library
import re

# Third-party
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.fields import get_error_detail
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import permissions, serializers
from controlpanel.api.models import App
from controlpanel.api.pagination import Auth0ApiPagination


class AppByNameViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    resource = "app"

    queryset = App.objects.all()

    serializer_class = serializers.AppSerializer
    permission_classes = (permissions.AppPermissions | permissions.AppJwtPermissions,)
    filter_backends = (DjangoFilterBackend,)
    lookup_field = "name"

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        mapping = {
            "customers": serializers.AppCustomerSerializer,
            "add_customers": serializers.AppCustomerSerializer,
            "delete_customers": serializers.DeleteAppCustomerSerializer,
        }
        serializer = mapping.get(self.action)
        if serializer:
            return serializer
        return super().get_serializer_class(*args, **kwargs)

    @action(detail=True, methods=["get"])
    def customers(self, request, *args, **kwargs):
        if "env_name" not in request.query_params:
            raise ValidationError({"env_name": "This field is required."})

        app = self.get_object()
        env_name = request.query_params.get("env_name")
        group_id = app.get_group_id(env_name)
        if not group_id:
            raise ValidationError({"env_name": f"No envorinment with name {env_name} found."})
        page_number = request.query_params.get("page", 1)
        per_page = request.query_params.get("per_page", 25)
        customers = app.customer_paginated(
            page=page_number,
            group_id=group_id,
            per_page=per_page,
        )
        serializer = self.get_serializer(data=customers["users"], many=True)
        serializer.is_valid()
        pagination = Auth0ApiPagination(
            request,
            page_number,
            object_list=serializer.validated_data,
            total_count=customers["total"],
            per_page=per_page,
        )
        return pagination.get_paginated_response()

    @customers.mapping.post
    def add_customers(self, request, *args, **kwargs):
        if "env_name" not in request.query_params:
            raise ValidationError({"env_name": "This field is required."})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        app = self.get_object()

        delimiters = re.compile(r"[,; ]+")
        emails = delimiters.split(serializer.validated_data["email"])
        errors = []
        for email in emails:
            validator = EmailValidator(message=f"{email} is not a valid email address")
            try:
                validator(email)
            except DjangoValidationError as error:
                errors.extend(get_error_detail(error))
        if errors:
            raise ValidationError(errors)

        app.add_customers(emails, env_name=request.query_params.get("env_name", ""))

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @customers.mapping.delete
    def delete_customers(self, request, *args, **kwargs):
        """
        Delete a customer from an environment. Requires the customers email and the env name.
        """
        app = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            app.delete_customer_by_email(
                serializer.validated_data["email"], env_name=serializer.validated_data["env_name"]
            )
        except app.DeleteCustomerError as error:
            raise ValidationError({"email": error.args[0]})

        return Response(status=status.HTTP_204_NO_CONTENT)
