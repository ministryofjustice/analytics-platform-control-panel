# Third-party
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import serializers
from controlpanel.utils import start_background_task


class ToolDeploymentAPIView(GenericAPIView):

    http_method_names = ["post"]
    serializer_class = serializers.ToolDeploymentSerializer
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        # TODO this is kept for legacy reasons, where the action is passed as a URL parameter. We
        # may want to remove to either pass the action in the POST data, or remove the action
        # entirely as currently it is only used for deploying a tool anyway.
        if self.kwargs["action"] != "deploy":
            return Response(status=status.HTTP_400_BAD_REQUEST)
        self.serializer = self.get_serializer(data=request.data, request=request)
        self.serializer.is_valid(raise_exception=True)
        self.serializer.save()
        return Response(status=status.HTTP_200_OK)
