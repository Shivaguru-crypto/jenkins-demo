pipeline {
    agent any

    environment {
        IMAGE_NAME = 'flask-jenkins-app'
        CONTAINER_NAME = 'flask-running'
        APP_PORT = '5000'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Pulling code from GitHub...'
                checkout scm
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Running tests before building Docker image...'
                sh '''
                    python3 -m pytest test_app.py -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Building Docker image...'
                sh '''
                    docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest
                    echo "✅ Docker image built: ${IMAGE_NAME}:${BUILD_NUMBER}"
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }

        stage('Stop Old Container') {
            steps {
                echo '🛑 Stopping old container if running...'
                sh '''
                    docker stop ${CONTAINER_NAME} || true
                    docker rm ${CONTAINER_NAME} || true
                    echo "✅ Old container removed"
                '''
            }
        }

        stage('Run New Container') {
            steps {
                echo '🚀 Starting new Docker container...'
                sh '''
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        -p ${APP_PORT}:5000 \
                        --restart unless-stopped \
                        ${IMAGE_NAME}:latest
                    echo "✅ Container started!"
                    docker ps | grep ${CONTAINER_NAME}
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                echo '🌐 Verifying container is responding...'
                sh '''
                    sleep 3
                    curl -s http://localhost:5000/ | python3 -m json.tool
                    curl -s http://localhost:5000/health | python3 -m json.tool
                    echo "✅ Flask running inside Docker on port 5000!"
                '''
            }
        }
    }

    post {
        success {
            echo '🎉 Docker deployment successful!'
            sh 'docker ps | grep flask'
        }
        failure {
            echo '❌ Pipeline failed!'
            sh 'docker logs ${CONTAINER_NAME} || true'
        }
    }
}
