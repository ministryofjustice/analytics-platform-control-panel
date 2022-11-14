from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework import status

from controlpanel.frontend.consumers import start_background_task


class ToolDeploymentAPIView(GenericAPIView):

    http_method_names = ['post']

    def _deploy(self, chart_name, tool_version, data):
        """
        This is the most backwards thing you'll see for a while. The helm
        task to deploy the tool apparently must happen when the view class
        attempts to redirect to the target url. I'm sure there's a good
        reason why.
        """
        # If there's already a tool deployed, we need to get this from a
        # hidden field posted back in the form. This is used by helm to delete
        # the currently installed chart for the tool before installing the
        # new chart.
        old_chart_name = data.get("deployed_chart_name", None)

        # Kick off the helm chart as a background task.
        start_background_task(
            "tool.deploy",
            {
                "tool_name": chart_name,
                "version": tool_version,
                "user_id": self.request.user.id,
                "id_token": self.request.user.get_id_token(),
                "old_chart_name": old_chart_name,
            },
        )

    def post(self, request, *args, **kwargs):
        chart_name = self.kwargs["tool-name"]
        tool_version = self.kwargs["version"]
        tool_action = self.kwargs["action"]
        tool_action_function = getattr(self, f"_{tool_action}", None)
        if callable(tool_action_function):
            tool_action_function(chart_name, tool_version, request.data)

        return Response(status=status.HTTP_201_CREATED)
