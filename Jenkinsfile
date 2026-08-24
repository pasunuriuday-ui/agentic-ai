pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'python -m pip install --upgrade pip'
                sh 'pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                sh 'pytest -q'
            }
        }

        stage('Docker Build') {
            steps {
                sh 'docker build -t agentic-ai-api:${BUILD_NUMBER} .'
            }
        }
    }

    post {
        success {
            echo 'CI pipeline completed successfully.'
        }

        failure {
            echo 'CI pipeline failed.'
        }

        always {
            echo "Build: ${BUILD_NUMBER}"
        }
    }
}
