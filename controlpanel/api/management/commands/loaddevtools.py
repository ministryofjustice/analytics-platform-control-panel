# Standard library
import os
import tempfile
from datetime import datetime

# Third-party
import yaml
from django.core.management.base import CommandError
from django.core.management.commands import loaddata

# First-party/Local
from controlpanel.api.models import Tool


class Command(loaddata.Command):
    help = "Load examples of RStudio and JupyterLab tools into the database"

    def handle(self, *args, **options):

        for filename in args:

            if not filename.lower().endswith((".yaml", ".yml")):
                raise CommandError("loaddevtools expects to receive fixture(s) in YAML format")

            with open(filename) as fixture_file:
                fixture_yaml = yaml.safe_load(fixture_file)

            fixture_skip_inds = []

            for ind, tool in enumerate(fixture_yaml):

                if tool["model"] != "api.tool":
                    raise CommandError("loaddevtools should only be used for loading Tools")

                # Check for very similar tools; ask user before loading likely repeats
                matching_tools = Tool.objects.filter(
                    description=tool["fields"]["description"],
                    chart_name=tool["fields"]["chart_name"],
                    name=tool["fields"]["name"],
                    version=tool["fields"]["version"],
                )

                if matching_tools:
                    print(tool)
                    print(
                        "A tool with the same name, version etc. is already present in the database.\nDo you still want to load this tool? Y/n"  # noqa: E501
                    )
                    confirm = input()
                    if confirm.lower() not in ("y", "yes"):
                        fixture_skip_inds.append(ind)
                        continue

                if tool["fields"]["chart_name"] == "rstudio":
                    env_var_prefix = "RSTUDIO"
                elif tool["fields"]["chart_name"].startswith("jupyter-"):
                    env_var_prefix = "JUPYTER_LAB"
                else:
                    raise CommandError(
                        "Tool name should begin with either 'rstudio' or 'jupyter-*'"
                    )

                tool["fields"]["values"]["proxy.auth0.domain"] = os.environ[
                    f"{env_var_prefix}_AUTH_CLIENT_DOMAIN"
                ]
                tool["fields"]["values"]["proxy.auth0.clientId"] = os.environ[
                    f"{env_var_prefix}_AUTH_CLIENT_ID"
                ]
                tool["fields"]["values"]["proxy.auth0.clientSecret"] = os.environ[
                    f"{env_var_prefix}_AUTH_CLIENT_SECRET"
                ]

                if tool["fields"].get("created") is None or not tool["fields"]["created"]:
                    tool["fields"]["created"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ%Z")

                if tool["fields"].get("modified") is None or not tool["fields"]["modified"]:
                    tool["fields"]["modified"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ%Z")

            fixture_yaml = [
                tool for ind, tool in enumerate(fixture_yaml) if ind not in fixture_skip_inds
            ]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as configured_fixture_file:
                configured_fixture_file.write(yaml.dump(fixture_yaml))
                configured_fixture_file.flush()

                loaddata_args = [configured_fixture_file.name]
                super().handle(*loaddata_args, **options)
