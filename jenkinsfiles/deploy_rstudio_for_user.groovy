pipeline {

    parameters {
        string(name: 'USERNAME', description: 'Github username')
        string(
            name: 'DOCKER_TAG',
            defaultValue: 'latest',
            description: 'RStudio version image tag, from https://github.com/ministryofjustice/analytics-platform-rstudio/releases and https://quay.io/repository/mojanalytics/rstudio?tab=tags')
    }

    agent any

    stages {
        stage ("Decrypt secrets") {
            environment {
                GPG_KEY = credentials('analytics-ops-gpg.key')
            }
            steps {
                sh "git-crypt unlock ${GPG_KEY}"
            }
        }

        stage ("Deploy RStudio for user") {
            steps {
                sh "scripts/deploy_rstudio ${params.USERNAME} --tag=${params.DOCKER_TAG}"
            }
        }
    }
}
