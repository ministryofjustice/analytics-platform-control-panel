import os
import yaml

if __name__ == "__main__":

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

        tool["fields"]["values"]["authProxy.auth0.domain"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_DOMAIN"]
        tool["fields"]["values"]["authProxy.auth0.clientId"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_ID"]
        tool["fields"]["values"]["authProxy.auth0.clientSecret"] = os.environ[f"{env_var_prefix}_AUTH_CLIENT_SECRET"]

    with open(os.path.join("controlpanel", "api", "dev_fixtures", "tool_configured.yaml"), "w") as configured_fixture_file:
        yaml.dump(fixture_yaml, configured_fixture_file)           
