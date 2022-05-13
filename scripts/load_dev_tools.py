import os
import tempfile
import yaml

import django
from django.core import management

if __name__ == "__main__":

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controlpanel.settings")
    django.setup()

    with open(os.path.join("controlpanel", "api", "dev_fixtures", "tool.yaml")) as fixture_file:
        fixture_yaml = yaml.safe_load(fixture_file)

    for tool in fixture_yaml:

        if tool["fields"]["chart_name"] == "rstudio":
            env_var_prefix = "RSTUDIO"
        elif tool["fields"]["chart_name"].startswith("jupyter-"):
            env_var_prefix = "JUPYTER_LAB"
        elif tool["fields"]["chart_name"] == "airflow-sqlite":
            env_var_prefix = "AIRFLOW"
        else:
            raise Exception(f"chart_name of tool, {tool['fields']['chart_name']},  should be rstudio, jupyterlab-* or airflow-sqlite")

        if "authProxy.auth0.domain" in tool["fields"]["values"]:
            tool["fields"]["values"]["authProxy.auth0.domain"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_DOMAIN"]
            tool["fields"]["values"]["authProxy.auth0.clientId"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_ID"]
            tool["fields"]["values"]["authProxy.auth0.clientSecret"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_SECRET"]
        else:
            tool["fields"]["values"]["proxy.auth0.domain"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_DOMAIN"]
            tool["fields"]["values"]["proxy.auth0.clientId"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_ID"]
            tool["fields"]["values"]["proxy.auth0.clientSecret"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_SECRET"]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as configured_fixture_file:
        configured_fixture_file.write(yaml.dump(fixture_yaml))
        configured_fixture_file.flush()
        management.call_command("loaddata", configured_fixture_file.name)
