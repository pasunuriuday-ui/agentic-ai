pipeline {
    agent any

    environment {
        VENV = "${WORKSPACE}/.venv"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Create Python Virtual Environment') {
            steps {
                sh '''
                    rm -rf "$VENV"
                    python3 -m venv "$VENV"
                    "$VENV/bin/python" --version
                    "$VENV/bin/pip" --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    "$VENV/bin/python" -m pip install --upgrade pip
                    "$VENV/bin/pip" install -r requirements.txt
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    "$VENV/bin/python" -m pytest -q
                '''
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build -t agentic-ai-api:${BUILD_NUMBER} .
                '''
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