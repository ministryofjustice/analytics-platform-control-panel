import os
import tempfile
import yaml

from django.core.management.commands import loaddata
from django.core.management.base import CommandError

class Command(loaddata.Command):
    help = "Load examples of RStudio and JupyterLab tools into the database"

    def handle(self, *args, **options):

        with open(args[0]) as fixture_file:
            fixture_yaml = yaml.safe_load(fixture_file)

        for tool in fixture_yaml:

            if tool["fields"]["chart_name"] == "rstudio":
                env_var_prefix = "RSTUDIO"
            elif tool["fields"]["chart_name"].startswith("jupyter-"):
                env_var_prefix = "JUPYTER_LAB"
            else:
                raise CommandError("Tool name should begin with either 'rstudio' or 'jupyter-*'")

            tool["fields"]["values"]["proxy.auth0.domain"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_DOMAIN"]
            tool["fields"]["values"]["proxy.auth0.clientId"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_ID"]
            tool["fields"]["values"]["proxy.auth0.clientSecret"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_SECRET"]

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as configured_fixture_file:
                configured_fixture_file.write(yaml.dump(fixture_yaml))
                configured_fixture_file.flush()
                
                args[0] = configured_fixture_file.name
                super().handle(*args, **options)
