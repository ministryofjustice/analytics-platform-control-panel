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


class AppByNameViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    resource = "app"

    queryset = App.objects.all()

    serializer_class = serializers.AppSerializer
    permission_classes = (permissions.AppPermissions | permissions.AppJwtTokenResourcePermissions,)
    filter_backends = (DjangoFilterBackend,)
    lookup_field = "name"

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    # TODO need to add extra permissions app:customers for these to work
    @action(detail=True, methods=["get"])
    def customers(self, request, *args, **kwargs):
        app = self.get_object()
        customers = app.customers(request.GET.get("env_name", ""))
        serializer = self.get_serializer(data=customers, many=True)
        serializer.is_valid()

        return Response(serializer.data)

    @customers.mapping.post
    def add_customers(self, request, *args, **kwargs):
        # TODO check this to see if can be refactored
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

        app.add_customers(emails, env_name=request.GET.get("env_name", ""))

        return Response(serializer.data, status=status.HTTP_201_CREATED)
