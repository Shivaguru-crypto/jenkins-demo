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
        always {
            echo "📊 Build #${BUILD_NUMBER} status: ${currentBuild.currentResult}"
        }
        success {
            echo '🎉 PIPELINE COMPLETED SUCCESSFULLY!'
            
            // 1. Send Email
            mail to: "${NOTIFY_EMAIL}",
                 subject: "✅ Jenkins Build #${BUILD_NUMBER} PASSED — ${JOB_NAME}",
                 body: "Build SUCCESS!\n\nApp URL: http://localhost:5000\nView build: ${BUILD_URL}"

            // 2. Send Slack Ping
            sh """
                curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"✅ *SUCCESS:* Build #${BUILD_NUMBER} of Flask App is live on Port 5000!"}' \
                https://hooks.slack.com/services/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
            """
        }
        failure {
            echo '❌ PIPELINE FAILED — check logs above!'
            
            // 1. Send Email
            mail to: "${NOTIFY_EMAIL}",
                 subject: "❌ Jenkins Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                 body: "Build FAILED!\n\nCheck the console output for errors:\n${BUILD_URL}console"

            // 2. Send Slack Ping
            sh """
                curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"❌ *FAILED:* Build #${BUILD_NUMBER} broke! Someone check the Jenkins logs."}' \
                https://hooks.slack.com/services/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
            """
        }
    }
}
