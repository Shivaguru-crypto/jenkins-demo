pipeline {
    agent any

    environment {
        IMAGE_NAME        = 'flask-jenkins-app'
        STAGING_CONTAINER = 'flask-staging'
        PROD_CONTAINER    = 'flask-production'
        STAGING_PORT      = '5001'
        PROD_PORT         = '5000'
        NOTIFY_EMAIL      = 'shivaguru1207@gmail.com'
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
                sh 'python3 -m py_compile app.py     && echo "✅ app.py OK"'
                sh 'python3 -m py_compile test_app.py && echo "✅ test_app.py OK"'
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running 5 automated tests...'
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
                        -e BUILD_NUMBER=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'docker ps | grep flask-staging'
                echo '✅ Staging LIVE on port 5001'
            }
        }

        stage('Smoke Test Staging') {
            steps {
                echo '🔬 Stage 6: Smoke testing STAGING...'
                sh 'sleep 10'
                sh 'curl -sf http://localhost:5001/health | python3 -m json.tool'
                sh 'curl -sf http://localhost:5001/       | python3 -m json.tool'
                sh 'curl -sf http://localhost:5001/version | python3 -m json.tool'
                echo '✅ Staging smoke tests passed!'
            }
        }

        stage('Approval Gate') {
            steps {
                echo '⏸️ Stage 7: Waiting for production approval...'

                withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                    sh '''
                        curl -s -X POST \
                        -H 'Content-type: application/json' \
                        -d '{"text":"⏸️ APPROVAL NEEDED! Staging looks good. Approve production deploy at http://localhost:8080"}' \
                        $SLACK_URL
                    '''
                }

                timeout(time: 5, unit: 'MINUTES') {
                    input(
                        message: "Deploy Build #${BUILD_NUMBER} to PRODUCTION?",
                        ok: '✅ Deploy to Production!',
                        submitter: 'admin'
                    )
                }
                echo '✅ Approved!'
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 8: Deploying to PRODUCTION...'

                // Save previous build number for rollback
                script {
                    def prevBuild = currentBuild.previousSuccessfulBuild
                    if (prevBuild) {
                        env.PREV_BUILD = prevBuild.number.toString()
                        echo "Previous good build: #${env.PREV_BUILD}"
                    } else {
                        env.PREV_BUILD = '0'
                        echo "No previous build found"
                    }
                }

                sh 'docker stop  flask-production || true'
                sh 'docker rm    flask-production || true'
                sh 'sleep 2'
                sh '''
                    docker run -d \
                        --name flask-production \
                        -p 5000:5000 \
                        -e ENVIRONMENT=production \
                        -e APP_VERSION=${BUILD_NUMBER} \
                        -e BUILD_NUMBER=${BUILD_NUMBER} \
                        --restart unless-stopped \
                        flask-jenkins-app:latest
                '''
                sh 'docker ps | grep flask-production'
                echo '✅ Production LIVE on port 5000'
            }
        }

        stage('Health Check + Auto Rollback') {
            steps {
                echo '🌐 Stage 9: Health check with auto-rollback...'
                sh 'sleep 5'

                script {
                    // Run health check
                    def healthStatus = sh(
                        script: 'curl -sf -o /dev/null -w "%{http_code}" http://localhost:5000/health',
                        returnStdout: true
                    ).trim()

                    echo "Health check returned: ${healthStatus}"

                    if (healthStatus == '200') {
                        echo '✅ Health check PASSED! Production is healthy!'
                        sh 'curl -sf http://localhost:5000/ | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                    } else {
                        echo "❌ Health check FAILED! Status: ${healthStatus}"
                        echo "🔄 Starting AUTOMATIC ROLLBACK to build #${env.PREV_BUILD}..."

                        // Stop failed deployment
                        sh 'docker stop flask-production || true'
                        sh 'docker rm   flask-production || true'
                        sh 'sleep 2'

                        // Rollback to previous image
                        if (env.PREV_BUILD != '0') {
                            sh """
                                docker run -d \\
                                    --name flask-production \\
                                    -p 5000:5000 \\
                                    -e ENVIRONMENT=production \\
                                    -e APP_VERSION=ROLLBACK-${env.PREV_BUILD} \\
                                    -e BUILD_NUMBER=${env.PREV_BUILD} \\
                                    --restart unless-stopped \\
                                    flask-jenkins-app:${env.PREV_BUILD}
                            """
                            echo "✅ Rolled back to build #${env.PREV_BUILD}"

                            // Notify rollback happened
                            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                                sh """
                                    curl -s -X POST \\
                                    -H 'Content-type: application/json' \\
                                    -d '{"text":"🔄 AUTO ROLLBACK! Build #${BUILD_NUMBER} failed health check. Rolled back to #${env.PREV_BUILD}!"}' \\
                                    \$SLACK_URL
                                """
                            }
                        } else {
                            echo "⚠️ No previous build to rollback to!"
                        }

                        // Fail the pipeline so team knows
                        error("Production health check failed! Rolled back to #${env.PREV_BUILD}")
                    }
                }
            }
        }

        stage('Image Cleanup') {
            steps {
                echo '🧹 Stage 10: Keeping only last 3 images...'
                sh '''
                    # Remove old images — keep only 3 most recent
                    docker images | grep flask-jenkins-app | grep -v latest | \
                    awk '{print $1":"$2}' | \
                    sort -t: -k2 -rn | \
                    tail -n +4 | \
                    xargs docker rmi -f 2>/dev/null || true

                    echo "✅ Cleanup done! Remaining images:"
                    docker images | grep flask-jenkins-app
                '''
            }
        }
    }

    post {

        success {
            echo '🎉 COMPLETE CD PIPELINE PASSED!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "✅ Build #${BUILD_NUMBER} DEPLOYED SUCCESSFULLY — ${JOB_NAME}",
                body: """
CD Pipeline SUCCESS!

Build:          #${BUILD_NUMBER}
Status:         DEPLOYED ✅
Staging:        http://localhost:5001
Production:     http://localhost:5000
Health Check:   http://localhost:5000/health
Version:        http://localhost:5000/version

View build: ${BUILD_URL}
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"🚀 BUILD DEPLOYED! All stages passed. Production live on port 5000!"}' \
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

Build:  #${BUILD_NUMBER}
Status: FAILED ❌

Check logs: ${BUILD_URL}console

If rollback occurred — production is running previous version.
                """
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"❌ PIPELINE FAILED! Check Jenkins logs immediately!"}' \
                    $SLACK_URL
                '''
            }
        }

        aborted {
            echo '⏱️ PIPELINE ABORTED!'

            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "⏱️ Build #${BUILD_NUMBER} ABORTED — Approval timed out",
                body: "Nobody approved production deployment. Build aborted safely."
            )

            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh '''
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"⏱️ APPROVAL TIMED OUT! Build aborted. Production unchanged."}' \
                    $SLACK_URL
                '''
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
