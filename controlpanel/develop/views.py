import json
import subprocess
from os import environ
from typing import List

from controlpanel.api.models import User
from controlpanel.api.kubernetes import KubernetesClient
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

def run_command(command, *args):
        env = environ.copy()
        bits = command.split()
        command = bits[0]
        args = bits[1:]
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
    breakpoint()
    return []


def user_selected_tool(username: str, toolname: str) -> str:
    # TODO: Create/Ensure instance of the named tool

    return f"Install {toolname} for {username}"


# @login_required()
@api_view()
@permission_classes([AllowAny])
def is_kube_connected_view(request):
    k8s = KubernetesClient(use_cpanel_creds=True)
    default_deployments = k8s.AppsV1Api.list_namespaced_deployment("default")
    # breakpoint()
    return Response(default_deployments.to_dict())