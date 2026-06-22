pipeline {
    agent any

    environment {
        IMAGE_NAME       = 'flask-jenkins-app'
        STAGING_CONTAINER  = 'flask-staging'
        PROD_CONTAINER   = 'flask-production'
        STAGING_PORT     = '5001'
        PROD_PORT        = '5000'
        NOTIFY_EMAIL     = 'shivaguru1207@gmail.com'
    }

    stages {

        stage('Checkout') {
            steps {
                echo '📥 Stage 1: Pulling latest code...'
                checkout scm
                sh 'echo "Commit: $(git log -1 --pretty=%B)"'
                sh 'echo "Author: $(git log -1 --pretty=%an)"'
                sh 'ls -la'
            }
        }

        stage('Code Quality') {
            steps {
                echo '🔍 Stage 2: Checking code quality...'
                sh 'python3 -m py_compile app.py    && echo "✅ app.py OK"'
                sh 'python3 -m py_compile test_app.py && echo "✅ test_app.py OK"'
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running 4 automated tests...'
                sh 'python3 -m pytest test_app.py -v --tb=short'
                echo '✅ All tests passed — safe to deploy!'
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Stage 4: Building Docker image...'
                sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
                sh 'docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest'
                sh 'echo "✅ Image built: ${IMAGE_NAME}:${BUILD_NUMBER}"'
                sh 'docker images | grep ${IMAGE_NAME}'
            }
        }

        stage('Deploy to Staging') {
            steps {
                echo '🔶 Stage 5: Deploying to STAGING environment...'
                sh 'docker stop  ${STAGING_CONTAINER} || true'
                sh 'docker rm    ${STAGING_CONTAINER} || true'
                sh '''
                    docker run -d \
                        --name flask-staging \
                        -p 5001:5000 \
                        -e ENVIRONMENT=staging \
                        -e APP_VERSION=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'echo "✅ Staging deployed on port 5001"'
                sh 'docker ps | grep flask-staging'
            }
        }

        stage('Smoke Test Staging') {
            steps {
                echo '🔬 Stage 6: Running smoke tests on STAGING...'
                sh 'sleep 5'
                sh '''
                    echo "Testing staging health..."
                    HEALTH=$(curl -sf http://localhost:5001/health | python3 -m json.tool)
                    echo "$HEALTH"

                    echo "Testing staging home..."
                    HOME=$(curl -sf http://localhost:5001/ | python3 -m json.tool)
                    echo "$HOME"

                    echo "Testing staging version..."
                    VERSION=$(curl -sf http://localhost:5001/version | python3 -m json.tool)
                    echo "$VERSION"

                    echo "Verifying environment is staging..."
                    curl -sf http://localhost:5001/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['\''environment'\''] == '\''staging'\'', '\''ERROR: Wrong environment!'\''
print('\''✅ Staging environment verified!'\'')
"
                '''
                echo '✅ All staging smoke tests passed!'
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 7: Deploying to PRODUCTION...'
                sh 'docker stop  ${PROD_CONTAINER} || true'
                sh 'docker rm    ${PROD_CONTAINER} || true'
                sh '''
                    docker run -d \
                        --name flask-production \
                        -p 5000:5000 \
                        -e ENVIRONMENT=production \
                        -e APP_VERSION=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'echo "✅ Production deployed on port 5000"'
                sh 'docker ps | grep flask-production'
            }
        }

        stage('Health Check Production') {
            steps {
                echo '🌐 Stage 8: Verifying PRODUCTION health...'
                sh 'sleep 5'
                sh 'curl -sf http://localhost:5000/health  | python3 -m json.tool'
                sh 'curl -sf http://localhost:5000/        | python3 -m json.tool'
                sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                echo '✅ Production is LIVE and healthy!'
            }
        }

        stage('Cleanup') {
            steps {
                echo '🧹 Stage 9: Cleaning old Docker images...'
                sh 'docker image prune -f || true'
                sh 'docker images | grep ${IMAGE_NAME}'
            }
        }
    }

    post {

        success {
            echo '🎉 FULL CD PIPELINE PASSED!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "✅ Build #${BUILD_NUMBER} PASSED — ${JOB_NAME}",
                body: """
CD Pipeline SUCCESS!

Job:         ${JOB_NAME}
Build:       #${BUILD_NUMBER}
Status:      PASSED ✅

Staging URL:    http://localhost:5001
Production URL: http://localhost:5000

View build: ${BUILD_URL}
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"✅ CD PIPELINE PASSED! Staging: port 5001 | Production: port 5000 | All smoke tests passed!"}' \
                    $SLACK_URL
                '''
            }
        }

        failure {
            echo '❌ CD PIPELINE FAILED!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "❌ Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                body: """
CD Pipeline FAILED!

Job:    ${JOB_NAME}
Build:  #${BUILD_NUMBER}
Status: FAILED ❌

Check the console output:
${BUILD_URL}console

Production was NOT updated — still running previous version.
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"❌ CD PIPELINE FAILED! Production was NOT updated. Check Jenkins logs immediately!"}' \
                    $SLACK_URL
                '''
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
