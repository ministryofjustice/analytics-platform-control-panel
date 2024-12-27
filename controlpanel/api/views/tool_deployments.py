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

    def _deploy(self, chart_name, data):
        """
        This is the most backwards thing you'll see for a while. The helm
        task to deploy the tool apparently must happen when the view class
        attempts to redirect to the target url. I'm sure there's a good
        reason why.
        """
        # The selected option from the "version" select control contains the
        # data we need.
        chart_info = data.get("version")
        # The tool name and version are stored in the selected option's value
        # attribute and then split on "__" to extract them. Why? Because we
        # need both pieces of information to kick off the background helm
        # deploy.
        tool_name, tool_version, tool_id = chart_info.split("__")

        # Kick off the helm chart as a background task.
        start_background_task(
            "tool.deploy",
            {
                "tool_name": chart_name,
                "version": tool_version,
                "tool_id": tool_id,
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
            },
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        chart_name = self.kwargs["tool_name"]
        tool_action = self.kwargs["action"]
        tool_action_function = getattr(self, f"_{tool_action}", None)
        if tool_action_function and callable(tool_action_function):
            tool_action_function(chart_name, request.data)
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
