#!groovy

pipeline {

  agent any

  stages {

    stage("Deploy") {
      steps {
        script {
          deploy.controlpanel(debug: true)
        }
      }
    }

  }
}
