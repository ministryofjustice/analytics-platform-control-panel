#!groovy

pipeline {

  parameters {
    string(
      name: "BRANCH",
      description: "Git branch or commit to deploy",
      defaultValue: env.BRANCH_NAME
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
          chart: "mojanalytics/cpanel-0.1.0",
          values: "config/chart-env-config/${env.ENV}/cpanel.yml",
          overrides: [
            "API.Environment.DEBUG": "True",
            "API.Image.Tag": params.BRANCH
          ]
        )
      }
    }

  }
}
