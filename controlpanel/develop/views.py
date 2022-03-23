import json
import subprocess
from os import environ
from typing import List

from controlpanel.api.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from rest_framework.decorators import api_view
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
    breakpoint()
    return []


def user_selected_tool(username: str, toolname: str) -> str:
    # TODO: Create/Ensure instance of the named tool

    return f"Install {toolname} for {username}"


# @login_required()
@api_view()
def develop_index(request):
    raw_cmd = f"kubectl get pods -A -o json"
    raw_bits = raw_cmd.split()
    command = raw_bits[0]
    args = raw_bits[1:]
    out, err = run_command(command, *args)
    return Response(json.loads(out))