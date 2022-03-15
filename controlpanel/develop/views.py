from typing import List

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render


def installed_tools(username: str) -> List[str]:
    # TODO: Get a list of this user's installed tools and return
    # a list of string ["like", "this"]

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
