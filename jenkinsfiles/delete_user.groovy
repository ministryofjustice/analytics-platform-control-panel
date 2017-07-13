pipeline {

    parameters {
        string(name: 'USERNAME', description: 'Github username')
    }

    agent any

    stages {
        stage ("Delete platform user") {
            steps {
                sh "scripts/delete_user ${params.USERNAME}"
            }
        }
    }
}
