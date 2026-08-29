pipeline {
    agent any

    environment {
        // =========================================
        // APPLICATION SERVICES
        // =========================================
        OLLAMA_HOST = 'http://agent_llm:11434'
        LLM_MODEL   = 'llama3:latest'
        QDRANT_URL  = 'http://agent_vector_db:6333'

        // =========================================
        // DOCKER IMAGE
        // =========================================
        DOCKER_IMAGE = 'agentic-ai-api'

        // =========================================
        // PYTORCH / CUDA
        // =========================================
        CUDA_VISIBLE_DEVICES = ''
        PYTORCH_ENABLE_MPS_FALLBACK = '1'
    }

    stages {

        // =========================================
        // 1. CHECKOUT
        // =========================================
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // =========================================
        // 2. SETUP PYTHON ENVIRONMENT
        // =========================================
        stage('Setup Python Environment') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "SETUP PYTHON ENVIRONMENT"
                    echo "========================================="

                    rm -rf .venv

                    python3 -m venv .venv

                    echo "Python version:"
                    .venv/bin/python --version

                    echo "Pip version:"
                    .venv/bin/pip --version
                '''
            }
        }

        // =========================================
        // 3. INSTALL DEPENDENCIES
        // =========================================
        stage('Install Dependencies') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "INSTALL DEPENDENCIES"
                    echo "========================================="

                    .venv/bin/pip install --upgrade pip

                    .venv/bin/pip install -r requirements.txt

                    echo "Dependencies installed successfully."
                '''
            }
        }

        // =========================================
        // 4. VERIFY REQUIRED SERVICES
        // =========================================
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

                    curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 30 \
                        "${OLLAMA_HOST}/api/tags"

                    echo
                    echo "Ollama connectivity: OK"

                    echo
                    echo "Checking Qdrant..."

                    curl \
                        --fail \
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

        // =========================================
        // 5. CHECK OLLAMA MODEL
        // =========================================
        stage('Ollama Model Check') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "CHECK OLLAMA MODEL"
                    echo "========================================="

                    RESPONSE=$(curl \
                        --fail \
                        --silent \
                        --show-error \
                        --max-time 30 \
                        "${OLLAMA_HOST}/api/tags")

                    echo
                    echo "Available Ollama models:"
                    echo "${RESPONSE}"

                    echo
                    echo "Checking required model: ${LLM_MODEL}"

                    echo "${RESPONSE}" | grep -q "\"name\":\"${LLM_MODEL}\""

                    echo
                    echo "Required model ${LLM_MODEL} is available."
                '''
            }
        }

        // =========================================
        // 6. UNIT TESTS
        // =========================================
        stage('Unit Tests') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "RUN UNIT TESTS"
                    echo "========================================="

                    .venv/bin/pytest -m "not integration" -v

                    echo
                    echo "Unit tests completed successfully."
                '''
            }
        }

        // =========================================
        // 7. LLM INTEGRATION TESTS
        // =========================================
        stage('LLM Integration Tests') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    sh '''
                        set -e

                        echo "========================================="
                        echo "RUN LLM INTEGRATION TESTS"
                        echo "========================================="

                        .venv/bin/pytest -m integration -v

                        echo
                        echo "LLM integration tests completed successfully."
                    '''
                }
            }
        }

        // =========================================
        // 8. SONARQUBE ANALYSIS
        // =========================================
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

                            echo "SonarQube analysis completed successfully."
                        """
                    }
                }
            }
        }

        // =========================================
        // 9. QUALITY GATE
        // =========================================
        stage('Quality Gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {

                    echo "========================================="
                    echo "WAITING FOR SONARQUBE QUALITY GATE"
                    echo "========================================="

                    waitForQualityGate(
                        abortPipeline: true
                    )

                    echo "SonarQube Quality Gate passed."
                }
            }
        }

        // =========================================
        // 10. DOCKER BUILD
        // =========================================
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
                    echo "Docker image:"
                    docker images ${DOCKER_IMAGE}:${BUILD_NUMBER}
                '''
            }
        }
    }

    // =============================================
    // POST ACTIONS
    // =============================================
    post {

        success {
            echo "========================================="
            echo "CI/CD PIPELINE SUCCESS"
            echo "========================================="

            echo "Build: ${BUILD_NUMBER}"
            echo "Image: ${DOCKER_IMAGE}:${BUILD_NUMBER}"

            echo "========================================="
        }

        failure {
            echo "========================================="
            echo "CI/CD PIPELINE FAILED"
            echo "========================================="

            echo "Build: ${BUILD_NUMBER}"

            echo "========================================="
        }

        always {
            echo "========================================="
            echo "BUILD FINISHED"
            echo "Build: ${BUILD_NUMBER}"
            echo "========================================="
        }
    }
}