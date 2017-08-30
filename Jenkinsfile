#!groovy

pipeline {

  parameters {
    string(
      name: "VERSION",
      description: "Version number of the control-panel to deploy",
      defaultValue: "0.1.0"
    )
  }

  agent any

  environment {
    DOCKER_REGISTRY="quay.io/mojanalytics/control-panel"
  }

  stages {

    stage("Deploy") {
      steps {
        helm.upgrade(
          release: "cpanel",
          chart: "mojanalytics/cpanel-${params.VERSION}",
          values: "config/chart-env-config/${env.ENV}/cpanel.yml",
          overrides: [
            "API.Environment.DEBUG": "True"
          ]
        )
      }
    }

  }
}
