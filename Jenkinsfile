pipeline {
    agent any

    environment {
        IMAGE_NAME     = 'flask-jenkins-app'
        CONTAINER_NAME = 'flask-production'
        APP_PORT       = '5000'
        NOTIFY_EMAIL   = 'your-email@gmail.com'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Stage 1: Pulling latest code...'
                checkout scm
                sh 'echo "Commit: $(git log -1 --pretty=%B)"'
                sh 'echo "Author: $(git log -1 --pretty=%an)"'
            }
        }

        stage('Code Quality') {
            steps {
                echo '🔍 Stage 2: Checking code quality...'
                sh 'python3 -m py_compile app.py && echo "✅ app.py OK"'
                sh 'python3 -m py_compile test_app.py && echo "✅ test_app.py OK"'
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running tests...'
                sh 'python3 -m pytest test_app.py -v --tb=short'
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Stage 4: Building Docker image...'
                sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
                sh 'docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest'
            }
        }

        stage('Deploy') {
            steps {
                echo '🚀 Stage 5: Deploying...'
                sh 'docker stop ${CONTAINER_NAME} || true'
                sh 'docker rm   ${CONTAINER_NAME} || true'
                sh '''docker run -d \
                    --name ${CONTAINER_NAME} \
                    -p ${APP_PORT}:5000 \
                    --restart unless-stopped \
                    ${IMAGE_NAME}:latest'''
            }
        }

        stage('Health Check') {
            steps {
                echo '🌐 Stage 6: Health Check...'
                sh 'sleep 5'
                sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
            }
        }
    }

    post {
        success {
            // ✅ EMAIL on success
            mail to: "${NOTIFY_EMAIL}",
                 subject: "✅ Jenkins Build #${BUILD_NUMBER} PASSED — ${JOB_NAME}",
                 body: """
Build SUCCESS!

Job:    ${JOB_NAME}
Build:  #${BUILD_NUMBER}
Status: PASSED ✅

Changes: ${env.GIT_COMMIT}
App URL: http://localhost:5000

View build: ${BUILD_URL}
                 """

            // ✅ SLACK on success
            slackSend(
                color: 'good',
                message: """✅ *BUILD PASSED* — ${JOB_NAME} #${BUILD_NUMBER}
- Status: SUCCESS
- App: http://localhost:5000/health
- Build: ${BUILD_URL}
- Commit: ${env.GIT_COMMIT?.take(7)}"""
            )
        }

        failure {
            // ❌ EMAIL on failure
            mail to: "${NOTIFY_EMAIL}",
                 subject: "❌ Jenkins Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                 body: """
Build FAILED!

Job:    ${JOB_NAME}
Build:  #${BUILD_NUMBER}
Status: FAILED ❌

Check the console output for errors:
${BUILD_URL}console

Fix the issue and push again.
                 """

            // ❌ SLACK on failure
            slackSend(
                color: 'danger',
                message: """❌ *BUILD FAILED* — ${JOB_NAME} #${BUILD_NUMBER}
- Status: FAILURE
- Check logs: ${BUILD_URL}console
- Fix and push again!"""
            )
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
