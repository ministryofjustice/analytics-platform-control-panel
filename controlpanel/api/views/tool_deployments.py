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

    def _deploy(self):
        """
        Call background task to deploy the tool.
        """
        start_background_task(
            "tool.deploy",
            {
                "tool_id": self.serializer.validated_data["tool"].id,
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
            },
        )

    def post(self, request, *args, **kwargs):
        self.serializer = self.get_serializer(data={"tool": request.data.get("version")})
        self.serializer.is_valid(raise_exception=True)

        tool_action = self.kwargs["action"]
        tool_action_function = getattr(self, f"_{tool_action}", None)
        if tool_action_function and callable(tool_action_function):
            tool_action_function()
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
