import os

from django.contrib import messages
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timesince import timesince
import jinja2
import misaka


markdown = misaka.Markdown(misaka.HtmlRenderer())


def render_markdown(text):
    return jinja2.Markup(markdown(text))


def environment(**kwargs):
    env = jinja2.Environment(**kwargs)

    env.filters["markdown"] = render_markdown
    env.globals.update(
        {
            "env": os.environ.get("ENV", "dev"),
            "get_messages": messages.get_messages,
            "timesince": timesince,
            "static": static,
            "url": reverse,
        }
    )

    return env
