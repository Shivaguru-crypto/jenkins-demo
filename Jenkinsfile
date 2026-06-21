pipeline {
    agent any

    environment {
        IMAGE_NAME     = 'flask-jenkins-app'
        CONTAINER_NAME = 'flask-production'
        APP_PORT       = '5000'
    }

    stages {

        stage('Checkout') {
            steps {
                echo '📥 Stage 1: Pulling latest code from GitHub...'
                checkout scm
                sh '''
                    echo "Commit: $(git log -1 --pretty=%B)"
                    echo "Author: $(git log -1 --pretty=%an)"
                    ls -la
                '''
            }
        }

        stage('Code Quality Check') {
            steps {
                echo '🔍 Stage 2: Checking code quality...'
                sh '''
                    python3 -m py_compile app.py
                    echo "✅ app.py syntax OK"
                    python3 -m py_compile test_app.py
                    echo "✅ test_app.py syntax OK"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running automated tests...'
                sh '''
                    python3 -m pytest test_app.py -v --tb=short
                    echo "✅ All tests passed!"
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Stage 4: Building Docker image...'
                sh '''
                    docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest
                    echo "✅ Image built: ${IMAGE_NAME}:${BUILD_NUMBER}"
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 5: Deploying container...'
                sh '''
                    docker stop ${CONTAINER_NAME} || true
                    docker rm   ${CONTAINER_NAME} || true
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        -p ${APP_PORT}:5000 \
                        --restart unless-stopped \
                        ${IMAGE_NAME}:latest
                    echo "✅ Container deployed!"
                    docker ps | grep ${CONTAINER_NAME}
                '''
            }
        }

        stage('Health Check') {
            steps {
                echo '🌐 Stage 6: Verifying deployment...'
                sh '''
                    sleep 5
                    curl -sf http://localhost:5000/ | python3 -m json.tool
                    curl -sf http://localhost:5000/health | python3 -m json.tool
                    curl -sf http://localhost:5000/add/10/20 | python3 -m json.tool
                    echo "✅ All health checks passed!"
                '''
            }
        }

        stage('Cleanup') {
            steps {
                echo '🧹 Stage 7: Cleaning old Docker images...'
                sh '''
                    docker image prune -f || true
                    echo "✅ Cleanup done!"
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }
    }

    post {
        success {
            echo '🎉 PIPELINE COMPLETED SUCCESSFULLY!'
            echo "✅ Build #${BUILD_NUMBER} — App live on port 5000"
        }
        failure {
            echo '❌ PIPELINE FAILED — check logs above!'
        }
        always {
            echo "📊 Build #${BUILD_NUMBER} status: ${currentBuild.currentResult}"
        }
    }
}
