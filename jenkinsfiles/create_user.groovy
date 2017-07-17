pipeline {

    parameters {
        string(name: 'USERNAME', description: 'Github username')
        string(name: 'EMAIL', description: 'Email address of the user')
        string(name: 'FULLNAME', description: 'Full name of the user')
    }

    agent any

    environment {
        GPG_KEY = credentials('analytics-ops-gpg.key')
        GITHUB_TOKEN = credentials('GITHUB_TOKEN')
    }

    stages {
        stage ("Decrypt secrets") {
            steps {
                sh "git-crypt unlock ${GPG_KEY}"
            }
        }

        stage ("Create platform user") {
            steps {
                sh "scripts/create_user ${params.USERNAME} ${params.EMAIL} --fullname '${params.FULLNAME}'"
            }
        }
    }
}
