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
        stage ("Fetch config") {
            environment {
                GPG_KEY = credentials('analytics-ops-gpg.key')
            }
            steps {
                dir('config') {
                    git 'https://github.com/ministryofjustice/analytics-platform-config'
                    sh "git-crypt unlock ${GPG_KEY}"
                }
            }
        }

        stage ("Deploy RStudio for user") {
            steps {
                sh "scripts/deploy_rstudio ${params.USERNAME} --tag=${params.DOCKER_TAG}"
            }
        }
    }
}
