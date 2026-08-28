pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/python --version
                    .venv/bin/pip --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    .venv/bin/pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    .venv/bin/pytest -q
                '''
            }
        }

        stage('SonarQube Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '''
                        SONAR_SCANNER=$(tool 'SonarScanner')

                        "$SONAR_SCANNER/bin/sonar-scanner" \
                          -Dsonar.projectKey=agentic-ai \
                          -Dsonar.projectName=agentic-ai \
                          -Dsonar.sources=app \
                          -Dsonar.tests=tests \
                          -Dsonar.python.version=3.13
                    '''
                }
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