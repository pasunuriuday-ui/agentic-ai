pipeline {
    agent any

    environment {
        // ============================================================
        // APPLICATION SERVICES
        // ============================================================
        OLLAMA_HOST = 'http://agent_llm:11434'
        LLM_MODEL = 'llama3:latest'

        QDRANT_HOST = 'http://agent_vector_db:6333'
        QDRANT_URL = 'http://agent_vector_db:6333'

        EMBEDDING_MODEL = 'nomic-embed-text:latest'

        // Use the collection name already used by the application
        COLLECTION_NAME = 'agentic_ai'

        // ============================================================
        // DOCKER
        // ============================================================
        DOCKER_IMAGE = 'agentic-ai-api'

        // ============================================================
        // PYTHON / MEMORY
        // ============================================================
        CUDA_VISIBLE_DEVICES = ''
        PYTORCH_ENABLE_MPS_FALLBACK = '1'

        PYTHONUNBUFFERED = '1'
    }

    stages {

        // ============================================================
        // 1. CHECKOUT
        // ============================================================
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // ============================================================
        // 2. PYTHON ENVIRONMENT
        // ============================================================
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

        // ============================================================
        // 3. DEPENDENCIES
        // ============================================================
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

        // ============================================================
        // 4. VERIFY SERVICES
        // ============================================================
        stage('Verify Services') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "VERIFY REQUIRED SERVICES"
                    echo "========================================="

                    echo "OLLAMA_HOST=${OLLAMA_HOST}"
                    echo "LLM_MODEL=${LLM_MODEL}"
                    echo "QDRANT_HOST=${QDRANT_HOST}"
                    echo "QDRANT_URL=${QDRANT_URL}"
                    echo "EMBEDDING_MODEL=${EMBEDDING_MODEL}"
                    echo "COLLECTION_NAME=${COLLECTION_NAME}"

                    echo
                    echo "Checking Ollama..."

                    curl --fail \
                         --silent \
                         --show-error \
                         --connect-timeout 5 \
                         --max-time 30 \
                         "${OLLAMA_HOST}/api/tags"

                    echo
                    echo "Ollama connectivity: OK"

                    echo
                    echo "Checking Qdrant..."

                    curl --fail \
                         --silent \
                         --show-error \
                         --connect-timeout 5 \
                         --max-time 30 \
                         "${QDRANT_URL}/healthz"

                    echo
                    echo "Qdrant connectivity: OK"

                    echo
                    echo "All required services are reachable."
                '''
            }
        }

        // ============================================================
        // 5. OLLAMA MODEL CHECK
        // ============================================================
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
                        --connect-timeout 5 \
                        --max-time 30 \
                        "${OLLAMA_HOST}/api/tags")

                    echo "${RESPONSE}"

                    if echo "${RESPONSE}" | grep -q "\"name\":\"${LLM_MODEL}\""; then
                        echo
                        echo "Required model ${LLM_MODEL} is available."
                    else
                        echo
                        echo "[ERROR] Required model ${LLM_MODEL} is NOT available."
                        echo
                        echo "Run:"
                        echo "docker exec agent_llm ollama pull ${LLM_MODEL}"
                        exit 1
                    fi
                '''
            }
        }

        // ============================================================
        // 6. UNIT TESTS
        // ============================================================
        stage('Unit Tests') {
            steps {
                sh '''
                    set -e

                    echo "========================================="
                    echo "RUN UNIT TESTS"
                    echo "========================================="

                    echo "Python:"
                    .venv/bin/python --version

                    echo
                    echo "Environment:"
                    echo "OLLAMA_HOST=${OLLAMA_HOST}"
                    echo "QDRANT_HOST=${QDRANT_HOST}"
                    echo "LLM_MODEL=${LLM_MODEL}"

                    echo
                    echo "Running pytest..."

                    .venv/bin/python -m pytest \
                        -m "not integration" \
                        -q
                '''
            }
        }

        // ============================================================
        // 7. INTEGRATION TESTS
        // ============================================================
        stage('LLM Integration Tests') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    sh '''
                        set -e

                        echo "========================================="
                        echo "RUN LLM INTEGRATION TESTS"
                        echo "========================================="

                        echo "OLLAMA_HOST=${OLLAMA_HOST}"
                        echo "QDRANT_HOST=${QDRANT_HOST}"
                        echo "LLM_MODEL=${LLM_MODEL}"

                        .venv/bin/python -m pytest \
                            -m integration \
                            -q
                    '''
                }
            }
        }

        // ============================================================
        // 8. SONARQUBE
        // ============================================================
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

                            echo
                            echo "SonarQube analysis completed."
                        """
                    }
                }
            }
        }

        // ============================================================
        // 9. QUALITY GATE
        // ============================================================
        stage('Quality Gate') {
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        // ============================================================
        // 10. DOCKER BUILD
        // ============================================================
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

    // ================================================================
    // POST ACTIONS
    // ================================================================
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
            echo "========================================="

            echo "Build: ${BUILD_NUMBER}"
        }
    }
}