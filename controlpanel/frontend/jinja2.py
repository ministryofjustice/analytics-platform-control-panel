import os

from django.contrib import messages
from django.templatetags.static import static
from django.urls import reverse
import jinja2
import misaka


markdown = misaka.Markdown(misaka.HtmlRenderer())


def render_markdown(text):
    return jinja2.Markup(markdown(text))


def environment(**options):
    extensions = options.get("extensions", [])
    extensions.append("sass_processor.jinja2.ext.SassSrc")
    options["extensions"] = extensions
    env = jinja2.Environment(**options)
    env.filters["markdown"] = render_markdown
    env.globals.update(
        {
            "env": os.environ.get("ENV", "dev"),
            "get_messages": messages.get_messages,
            "static": static,
            "url": reverse,
        }
    )
    return env
