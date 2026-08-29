pipeline {
    agent any

    environment {
        // Application services
        OLLAMA_HOST  = 'http://agent_llm:11434'
        LLM_MODEL    = 'llama3:latest'
        QDRANT_URL   = 'http://agent_vector_db:6333'

        // Docker image
        DOCKER_IMAGE = 'agentic-ai-api'
        
        // Prevent PyTorch/CUDA from blowing up container memory during pytest
        CUDA_VISIBLE_DEVICES = ''
        PYTORCH_ENABLE_MPS_FALLBACK = '1'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "SETUP PYTHON ENVIRONMENT"
                    echo "========================================="

                    rm -rf .venv

                    python3 -m venv .venv

                    .venv/bin/python --version
                    .venv/bin/pip --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "INSTALL DEPENDENCIES"
                    echo "========================================="

                    .venv/bin/pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                '''
            }
        }

        stage('Verify Services') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "VERIFY REQUIRED SERVICES"
                    echo "========================================="

                    echo "OLLAMA_HOST=${OLLAMA_HOST}"
                    echo "LLM_MODEL=${LLM_MODEL}"
                    echo "QDRANT_URL=${QDRANT_URL}"

                    echo
                    echo "Checking Ollama..."

                    curl --fail \
                         --silent \
                         --show-error \
                         --max-time 30 \
                         "${OLLAMA_HOST}/api/tags"

                    echo
                    echo "Ollama connectivity: OK"

                    echo
                    echo "Checking Qdrant..."

                    curl --fail \
                         --silent \
                         --show-error \
                         --max-time 30 \
                         "${QDRANT_URL}/healthz"

                    echo
                    echo "Qdrant connectivity: OK"

                    echo
                    echo "All required services are reachable."
                '''
            }
        }

        stage('Ollama Model Check') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "CHECK OLLAMA MODEL"
                    echo "========================================="

                    RESPONSE=$(curl --fail \
                        --silent \
                        --show-error \
                        --max-time 30 \
                        "${OLLAMA_HOST}/api/tags")

                    echo "${RESPONSE}"

                    if echo "${RESPONSE}" | grep -q '"name":"${LLM_MODEL}"'; then
                        echo
                        echo "Required model ${LLM_MODEL} is available."
                    else
                        echo
                        echo "[ERROR] Required model ${LLM_MODEL} is NOT available."
                        echo
                        echo "Pull the model in the Ollama container before running Jenkins:"
                        echo
                        echo "docker exec agent_llm ollama pull ${LLM_MODEL}"
                        echo
                        exit 1
                    fi
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "RUN UNIT TESTS"
                    echo "========================================="

                    .venv/bin/pytest \
                        -m "not integration" \
                        -v
                '''
            }
        }

        stage('LLM Integration Tests') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {

                    sh '''
                        set -e

                        echo "========================================="
                        echo "RUN LLM INTEGRATION TESTS"
                        echo "========================================="

                        .venv/bin/pytest \
                            -m integration \
                            -v
                    '''
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {

                    echo "========================================="
                    echo "SONARQUBE ANALYSIS"
                    echo "========================================="

                    def sonarScannerHome = tool name: 'SonarScanner'

                    echo "SonarScanner home: ${sonarScannerHome}"

                    withSonarQubeEnv('SonarQube') {

                        sh """
                            set -e

                            echo "Running SonarScanner..."

                            "${sonarScannerHome}/bin/sonar-scanner" \
                              -Dsonar.projectKey=agentic-ai \
                              -Dsonar.projectName=agentic-ai \
                              -Dsonar.sources=app \
                              -Dsonar.tests=tests \
                              -Dsonar.python.version=3.13

                            echo "SonarQube analysis completed."
                        """
                    }
                }
            }
        }

        stage('Quality Gate') {
            steps {

                timeout(time: 10, unit: 'MINUTES') {

                    waitForQualityGate(
                        abortPipeline: true
                    )
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "BUILD DOCKER IMAGE"
                    echo "========================================="

                    docker build \
                        -t ${DOCKER_IMAGE}:${BUILD_NUMBER} \
                        .

                    echo
                    echo "Docker image built successfully."

                    echo
                    echo "Image:"
                    docker images ${DOCKER_IMAGE}:${BUILD_NUMBER}
                '''
            }
        }
    }

    post {

        success {
            echo "========================================="
            echo "CI/CD PIPELINE SUCCESS"
            echo "========================================="
            echo "Build: ${BUILD_NUMBER}"
            echo "Image: ${DOCKER_IMAGE}:${BUILD_NUMBER}"
        }

        failure {
            echo "========================================="
            echo "CI/CD PIPELINE FAILED"
            echo "========================================="
            echo "Build: ${BUILD_NUMBER}"
        }

        always {
            echo "========================================="
            echo "BUILD FINISHED"
            echo "Build: ${BUILD_NUMBER}"
            echo "========================================="
        }
    }
}