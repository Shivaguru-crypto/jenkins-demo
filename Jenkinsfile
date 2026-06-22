pipeline {
    agent any

    environment {
        IMAGE_NAME     = 'flask-jenkins-app'
        CONTAINER_NAME = 'flask-production'
        APP_PORT       = '5000'
        NOTIFY_EMAIL   = 'shivaguru1207@gmail.com'
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
                sh 'python3 -m py_compile app.py && echo "app.py OK"'
                sh 'python3 -m py_compile test_app.py && echo "test_app.py OK"'
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running automated tests...'
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
                echo '🚀 Stage 5: Deploying container...'
                sh 'docker stop ${CONTAINER_NAME} || true'
                sh 'docker rm   ${CONTAINER_NAME} || true'
                sh '''
                    docker run -d \
                        --name flask-production \
                        -p 5000:5000 \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'docker ps | grep flask-production'
            }
        }

        stage('Health Check') {
            steps {
                echo '🌐 Stage 6: Verifying deployment...'
                sh 'sleep 5'
                sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
                sh 'curl -sf http://localhost:5000/ | python3 -m json.tool'
                echo '✅ App is LIVE!'
            }
        }
    }

    post {

        success {
            echo '🎉 BUILD PASSED!'

            // Email notification
            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "✅ Build #${BUILD_NUMBER} PASSED — ${JOB_NAME}",
                body: "Build SUCCESS!\n\nApp URL: http://localhost:5000\nBuild URL: ${BUILD_URL}"
            )

            // Slack — webhook URL pulled from Jenkins Credentials safely
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"✅ BUILD PASSED! Flask app is LIVE on port 5000!"}' \
                    $SLACK_URL
                '''
            }
        }

        failure {
            echo '❌ BUILD FAILED!'

            // Email notification
            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "❌ Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                body: "Build FAILED!\n\nCheck logs: ${BUILD_URL}console"
            )

            // Slack — webhook URL pulled from Jenkins Credentials safely
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"❌ BUILD FAILED! Check Jenkins logs immediately!"}' \
                    $SLACK_URL
                '''
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
