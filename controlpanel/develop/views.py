import json
import subprocess
from os import environ
from typing import List

from controlpanel.api.kubernetes import get_config
from controlpanel.api.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from kubernetes import client, config
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def run_command(command, *args):
        env = environ.copy()
        output = subprocess.Popen(
            [command, *args],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf8",
            env=env,
        )
        out, err = output.communicate()
        return out, err


def installed_tools(username: str) -> List[str]:
    # TODO: Get a list of this user's installed tools and return
    # a list of string ["like", "this"]

    user = User.objects.get(username=username)
    raw_cmd = f"kubectl get tools -n user-{username} -o json"
    raw_bits = raw_cmd.split()
    command = raw_bits[0]
    args = raw_bits[1:]
    out, err = run_command(command, *args)

    return []


def user_selected_tool(username: str, toolname: str) -> str:
    # TODO: Create/Ensure instance of the named tool

    return f"Install {toolname} for {username}"


@login_required()
def develop_index(request):
    status = None
    tool = None

    if request.method == "POST":
        data = request.POST

        tool = data.get("tool", "")
        if not tool:
            status = "No tool selected"
        else:
            status = user_selected_tool(request.user, tool)

    return render(
        request,
        "develop/index.html",
        {
            "username": request.user,
            "status": status,
            "tool": tool,
            "installed_tools": installed_tools(request.user),
        },
    )


@api_view()
@permission_classes([AllowAny])
def is_kube_connected_view(request):
    """
    This view allows you to see if the kube cluster is connected in debug mode and shows a list of services and namespaces.
    """
    get_config()

    v1 = client.CoreV1Api()
    services = v1.list_service_for_all_namespaces()
    output = []
    for service in services.items:
        service_datum = {
            "service_name": service.metadata.name,
            "namespace": service.metadata.namespace
        }
        output.append(service_datum)
    return Response(output) 
