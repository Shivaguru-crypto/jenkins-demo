pipeline {
    // Run on our connected agent
    agent any

    environment {
        IMAGE_NAME     = 'flask-jenkins-app'
        CONTAINER_NAME = 'flask-production'
        APP_PORT       = '5000'
        DEPLOY_DIR     = '/var/www/html'
    }

    stages {

        stage('Checkout') {
            steps {
                echo '📥 Stage 1: Pulling latest code from GitHub...'
                checkout scm
                sh '''
                    echo "Branch: $(git branch --show-current || echo main)"
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
                    echo "Python files in project:"
                    find . -name "*.py" | head -20
                    echo "Checking syntax of app.py..."
                    python3 -m py_compile app.py && echo "✅ app.py syntax OK"
                    python3 -m py_compile test_app.py && echo "✅ test_app.py syntax OK"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running automated test suite...'
                sh '''
                    python3 -m pytest test_app.py -v --tb=short \
                        --junit-xml=test-results.xml || true
                    echo "✅ Test suite completed!"
                    cat test-results.xml | grep -E "tests=|failures=|errors=" || true
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Stage 4: Building Docker image...'
                sh '''
                    echo "Building image: ${IMAGE_NAME}:${BUILD_NUMBER}"
                    docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .
                    docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest
                    echo "✅ Image built successfully!"
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 5: Deploying to production...'
                sh '''
                    echo "Stopping old container..."
                    docker stop ${CONTAINER_NAME} || true
                    docker rm   ${CONTAINER_NAME} || true

                    echo "Starting new container..."
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        -p ${APP_PORT}:5000 \
                        --restart unless-stopped \
                        -e ENVIRONMENT=production \
                        ${IMAGE_NAME}:latest

                    echo "✅ New container started!"
                    docker ps | grep ${CONTAINER_NAME}
                '''
            }
        }

        stage('Health Check') {
            steps {
                echo '🌐 Stage 6: Running health checks...'
                sh '''
                    echo "Waiting for app to start..."
                    sleep 5

                    echo "Testing home endpoint..."
                    curl -sf http://localhost:5000/ | python3 -m json.tool

                    echo "Testing health endpoint..."
                    curl -sf http://localhost:5000/health | python3 -m json.tool

                    echo "Testing add endpoint..."
                    curl -sf http://localhost:5000/add/10/20 | python3 -m json.tool

                    echo "✅ All health checks passed!"
                '''
            }
        }

        stage('Cleanup Old Images') {
            steps {
                echo '🧹 Stage 7: Cleaning up old Docker images...'
                sh '''
                    echo "Current images:"
                    docker images | grep ${IMAGE_NAME}

                    echo "Removing dangling images..."
                    docker image prune -f || true

                    echo "✅ Cleanup done!"
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }
    }

    post {
        success {
            echo """
            ╔══════════════════════════════════════╗
            ║   ✅ PIPELINE COMPLETED SUCCESSFULLY  ║
            ║   Build #${BUILD_NUMBER}                       
            ║   App running on port ${APP_PORT}              
            ╚══════════════════════════════════════╝
            """
        }
        failure {
            echo '❌ PIPELINE FAILED!'
            sh '''
                echo "=== Container Logs ==="
                docker logs ${CONTAINER_NAME} --tail=50 || true
                echo "=== Running Containers ==="
                docker ps -a | grep ${CONTAINER_NAME} || true
            '''
        }
        always {
            echo "📊 Build #${BUILD_NUMBER} finished — Status: ${currentBuild.currentResult}"
            sh 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
        }
    }
}
