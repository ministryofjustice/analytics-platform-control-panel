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

  stages {

    stage("Deploy") {
      steps {
        script {
          deploy.controlpanel(debug: true, tag: params.BRANCH)
        }
      }
    }

  }
}
