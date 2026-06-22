pipeline {
    agent any

    environment {
        IMAGE_NAME         = 'flask-jenkins-app'
        STAGING_CONTAINER  = 'flask-staging'
        PROD_CONTAINER     = 'flask-production'
        STAGING_PORT       = '5001'
        PROD_PORT          = '5000'
        NOTIFY_EMAIL       = 'shivaguru1207@gmail.com'
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
                echo '✅ All tests passed!'
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
                echo '🔶 Stage 5: Deploying to STAGING...'
                sh 'docker stop  flask-staging || true'
                sh 'docker rm    flask-staging || true'
                sh 'sleep 2'
                sh '''
                    docker run -d \
                        --name flask-staging \
                        -p 5001:5000 \
                        -e ENVIRONMENT=staging \
                        -e APP_VERSION=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'docker ps | grep flask-staging'
                echo '✅ Staging is LIVE on port 5001'
            }
        }

        stage('Smoke Test Staging') {
            steps {
                echo '🔬 Stage 6: Smoke testing STAGING...'
                sh 'sleep 5'
                sh 'curl -sf http://localhost:5001/health | python3 -m json.tool'
                sh 'curl -sf http://localhost:5001/       | python3 -m json.tool'
                sh 'curl -sf http://localhost:5001/version | python3 -m json.tool'
                sh '''
                    RESULT=$(curl -sf http://localhost:5001/ | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get(chr(101)+chr(110)+chr(118)+chr(105)+chr(114)+chr(111)+chr(110)+chr(109)+chr(101)+chr(110)+chr(116), chr(117)+chr(110)+chr(107)+chr(110)+chr(111)+chr(119)+chr(110)))
")
                    echo "Environment detected: $RESULT"
                    echo "✅ Staging smoke test passed!"
                '''
            }
        }

        stage('🚦 Approval Gate') {
            steps {
                echo '⏸️ Stage 7: Waiting for PRODUCTION approval...'

                // Notify team that approval is needed
                withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                    sh '''
                        curl -s -X POST \
                        -H 'Content-type: application/json' \
                        -d '{"text":"⏸️ APPROVAL NEEDED! Build #${BUILD_NUMBER} passed staging. Go to Jenkins to approve production deploy: http://localhost:8080"}' \
                        $SLACK_URL
                    '''
                }

                // Wait for human to click Approve or Reject
                timeout(time: 5, unit: 'MINUTES') {
                    input(
                        message: "🚦 Deploy Build #${BUILD_NUMBER} to PRODUCTION?",
                        ok: '✅ YES — Deploy to Production!',
                        submitter: 'admin',
                        parameters: [
                            choice(
                                name: 'DEPLOY_REASON',
                                choices: ['Feature Release', 'Bug Fix', 'Hotfix', 'Rollback'],
                                description: 'Why are you deploying?'
                            )
                        ]
                    )
                }
                echo '✅ Production deployment APPROVED!'
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 8: Deploying to PRODUCTION...'
                sh 'docker stop  flask-production || true'
                sh 'docker rm    flask-production || true'
                sh 'sleep 2'
                sh '''
                    docker run -d \
                        --name flask-production \
                        -p 5000:5000 \
                        -e ENVIRONMENT=production \
                        -e APP_VERSION=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'docker ps | grep flask-production'
                echo '✅ Production is LIVE on port 5000'
            }
        }

        stage('Health Check Production') {
            steps {
                echo '🌐 Stage 9: Verifying PRODUCTION...'
                sh 'sleep 5'
                sh 'curl -sf http://localhost:5000/health  | python3 -m json.tool'
                sh 'curl -sf http://localhost:5000/        | python3 -m json.tool'
                sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                echo '✅ Production is healthy!'
            }
        }

        stage('Cleanup') {
            steps {
                echo '🧹 Stage 10: Cleaning old Docker images...'
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
                subject: "✅ Build #${BUILD_NUMBER} DEPLOYED to PRODUCTION — ${JOB_NAME}",
                body: """
CD Pipeline SUCCESS!

Job:            ${JOB_NAME}
Build:          #${BUILD_NUMBER}
Status:         DEPLOYED ✅

Staging URL:    http://localhost:5001
Production URL: http://localhost:5000
Health Check:   http://localhost:5000/health

View build: ${BUILD_URL}
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"🚀 PRODUCTION DEPLOYED! Build passed all gates. App live on port 5000!"}' \
                    $SLACK_URL
                '''
            }
        }

        failure {
            echo '❌ CD PIPELINE FAILED OR REJECTED!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "❌ Build #${BUILD_NUMBER} FAILED/REJECTED — ${JOB_NAME}",
                body: """
CD Pipeline FAILED or was REJECTED!

Job:    ${JOB_NAME}
Build:  #${BUILD_NUMBER}
Status: FAILED ❌

Production was NOT updated.
Check logs: ${BUILD_URL}console
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"❌ PIPELINE FAILED or REJECTED! Production was NOT updated. Check Jenkins logs!"}' \
                    $SLACK_URL
                '''
            }
        }

        aborted {
            echo '⏱️ PIPELINE ABORTED — Approval timed out!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "⏱️ Build #${BUILD_NUMBER} TIMED OUT — Nobody approved!",
                body: "Nobody approved production deployment within 5 minutes. Build aborted."
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"⏱️ APPROVAL TIMED OUT! Build aborted — nobody approved production in 5 minutes!"}' \
                    $SLACK_URL
                '''
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
