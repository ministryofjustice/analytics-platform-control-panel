# Standard library
import re

# Third-party
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
            "add_customers": serializers.AddAppCustomersSerializer,
            "delete_customers": serializers.DeleteAppCustomerSerializer,
        }
        serializer = mapping.get(self.action)
        if serializer:
            return serializer
        return super().get_serializer_class(*args, **kwargs)

    @action(detail=True, methods=["get"])
    def customers(self, request, *args, **kwargs):
        app = self.get_object()
        serializer = serializers.AppCustomersQueryParamsSerializer(
            data=request.query_params, app=app
        )
        serializer.is_valid(raise_exception=True)
        validated_params = serializer.validated_data

        group_id = app.get_group_id(validated_params["env_name"])
        customers = app.customer_paginated(
            page=validated_params["page"],
            group_id=group_id,
            per_page=validated_params["per_page"],
        )
        customers_serializer = self.get_serializer(data=customers["users"], many=True)
        customers_serializer.is_valid(raise_exception=True)

        return Auth0ApiPagination(
            request=request,
            page_number=validated_params["page"],
            object_list=customers_serializer.validated_data,
            total_count=customers["total"],
            per_page=validated_params["per_page"],
        ).get_paginated_response()

    @customers.mapping.post
    def add_customers(self, request, *args, **kwargs):
        app = self.get_object()
        serializer = self.get_serializer(data=request.data, app=app)
        serializer.is_valid(raise_exception=True)

        try:
            app.add_customers(
                serializer.validated_data["emails"], env_name=serializer.validated_data["env_name"]
            )
        except app.AddCustomerError:
            raise ValidationError(
                "An error occurred trying to add customers, check that the environment exists."
            )

        return Response(
            {"message": "Successfully added customers."}, status=status.HTTP_201_CREATED
        )

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
