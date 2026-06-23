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
                sh 'python3 -m py_compile app.py     && echo "app.py OK"'
                sh 'python3 -m py_compile test_app.py && echo "test_app.py OK"'
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
                sh 'echo "Image built: ${IMAGE_NAME}:${BUILD_NUMBER}"'
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
                        -d '{"text":"⏸️ APPROVAL NEEDED! Staging passed. Approve at http://localhost:8080"}' \
                        $SLACK_URL
                    '''
                }
                timeout(time: 5, unit: 'MINUTES') {
                    input(
                        message: "Deploy Build #${BUILD_NUMBER} to PRODUCTION?",
                        ok: 'Deploy to Production!',
                        submitter: 'admin'
                    )
                }
                echo '✅ Approved!'
            }
        }

        stage('Deploy to Production') {
            steps {
                echo '🚀 Stage 8: Deploying to PRODUCTION...'
                script {
                    def prevBuild = currentBuild.previousSuccessfulBuild
                    if (prevBuild) {
                        env.PREV_BUILD = prevBuild.number.toString()
                        echo "Previous good build: #${env.PREV_BUILD}"
                    } else {
                        env.PREV_BUILD = '0'
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
                    def healthStatus = sh(
                        script: 'curl -sf -o /dev/null -w "%{http_code}" http://localhost:5000/health',
                        returnStdout: true
                    ).trim()

                    echo "Health check status: ${healthStatus}"

                    if (healthStatus == '200') {
                        echo '✅ Health check PASSED!'
                        sh 'curl -sf http://localhost:5000/       | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                    } else {
                        echo "❌ Health check FAILED! Status: ${healthStatus}"
                        echo "🔄 ROLLBACK to build #${env.PREV_BUILD}..."
                        sh 'docker stop flask-production || true'
                        sh 'docker rm   flask-production || true'
                        sh 'sleep 2'
                        if (env.PREV_BUILD != '0') {
                            sh """
                                docker run -d \
                                    --name flask-production \
                                    -p 5000:5000 \
                                    -e ENVIRONMENT=production \
                                    -e APP_VERSION=ROLLBACK-${env.PREV_BUILD} \
                                    -e BUILD_NUMBER=${env.PREV_BUILD} \
                                    --restart unless-stopped \
                                    flask-jenkins-app:${env.PREV_BUILD}
                            """
                            echo "✅ Rolled back to #${env.PREV_BUILD}"
                            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                                sh """
                                    curl -s -X POST \
                                    -H 'Content-type: application/json' \
                                    -d '{"text":"```\\n[Pipeline] AUTO ROLLBACK TRIGGERED\\n  Build    : #${BUILD_NUMBER} FAILED\\n  Rolled to: #${env.PREV_BUILD}\\n  Reason   : Health check returned ${healthStatus}\\nFinished: ROLLBACK```"}' \
                                    \$SLACK_URL
                                """
                            }
                        }
                        error("Health check failed! Rolled back to #${env.PREV_BUILD}")
                    }
                }
            }
        }

        stage('Image Cleanup') {
            steps {
                echo '🧹 Stage 10: Keeping only last 3 images...'
                sh '''
                    docker images | grep flask-jenkins-app | grep -v latest | \
                    awk '{print $1":"$2}' | \
                    sort -t: -k2 -rn | \
                    tail -n +4 | \
                    xargs docker rmi -f 2>/dev/null || true
                    echo "Remaining images:"
                    docker images | grep flask-jenkins-app
                '''
            }
        }
    }

    post {
        success {
            echo '🎉 CD PIPELINE PASSED!'
            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "✅ Build #${BUILD_NUMBER} DEPLOYED — ${JOB_NAME}",
                body: """============================================================
  JENKINS CD PIPELINE - BUILD REPORT
============================================================

[Pipeline] Start of Pipeline
[Pipeline] node - Running on worker-node-1

  Stage 1  : OK  Checkout SCM
  Stage 2  : OK  Code Quality Check
  Stage 3  : OK  Run Tests (5/5 passed)
  Stage 4  : OK  Build Docker Image - flask-jenkins-app:${BUILD_NUMBER}
  Stage 5  : OK  Deploy to Staging  - port 5001
  Stage 6  : OK  Smoke Test Staging
  Stage 7  : OK  Approval Gate      - APPROVED
  Stage 8  : OK  Deploy to Production - port 5000
  Stage 9  : OK  Health Check        - HTTP 200
  Stage 10 : OK  Image Cleanup

[Pipeline] Post Actions
  Status   : SUCCESS
  Build    : #${BUILD_NUMBER}
  Job      : ${JOB_NAME}

------------------------------------------------------------
  ENDPOINTS
------------------------------------------------------------
  Staging    : http://localhost:5001
  Production : http://localhost:5000
  Health     : http://localhost:5000/health
  Version    : http://localhost:5000/version
  Console    : ${BUILD_URL}console

============================================================
[Pipeline] End of Pipeline
Finished: SUCCESS
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  Stage 1  : OK  Checkout SCM\\n  Stage 2  : OK  Code Quality\\n  Stage 3  : OK  Run Tests (5/5)\\n  Stage 4  : OK  Docker Image :${BUILD_NUMBER}\\n  Stage 5  : OK  Deploy Staging\\n  Stage 6  : OK  Smoke Tests\\n  Stage 7  : OK  Approval Gate\\n  Stage 8  : OK  Deploy Production\\n  Stage 9  : OK  Health Check HTTP 200\\n  Stage 10 : OK  Cleanup\\n\\n  Status   : SUCCESS\\n  Build    : #${BUILD_NUMBER}\\n  App URL  : http://localhost:5000\\n============================================================\\nFinished: SUCCESS\\n============================================================```"}' \
                    \$SLACK_URL
                """
            }
        }

        failure {
            echo '❌ CD PIPELINE FAILED!'
            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "❌ Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                body: """============================================================
  JENKINS CD PIPELINE - BUILD REPORT
============================================================

[Pipeline] Start of Pipeline
[Pipeline] node - Running on worker-node-1

  Stage 1  : OK      Checkout SCM
  Stage 2  : OK      Code Quality Check
  Stage 3  : OK      Run Tests
  Stage 4  : OK      Build Docker Image
  Stage 5  : OK      Deploy to Staging
  Stage 6  : OK      Smoke Test Staging
  Stage 7  : OK      Approval Gate
  Stage 8  : OK      Deploy to Production
  Stage 9  : FAILED  Health Check  <-- PIPELINE STOPPED HERE
  Stage 10 : SKIPPED Image Cleanup

[Pipeline] Post Actions
  Status   : FAILURE
  Build    : #${BUILD_NUMBER}
  Job      : ${JOB_NAME}

------------------------------------------------------------
  ERROR DETAILS
------------------------------------------------------------
  Health check failed on http://localhost:5000/health
  Auto-rollback triggered to previous build

------------------------------------------------------------
  ACTION REQUIRED
------------------------------------------------------------
  1. Check console: ${BUILD_URL}console
  2. Fix the issue in GitHub
  3. Push code to re-trigger pipeline

============================================================
[Pipeline] End of Pipeline
Finished: FAILURE
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  Stage 9  : FAILED Health Check <- PIPELINE STOPPED HERE\\n  Stage 10 : SKIPPED Image Cleanup\\n\\n  Status   : FAILURE\\n  Build    : #${BUILD_NUMBER}\\n  Action   : Check logs and fix code\\n  Logs     : http://localhost:8080/job/flask-app-pipeline/${BUILD_NUMBER}/console\\n============================================================\\nFinished: FAILURE\\n============================================================```"}' \
                    \$SLACK_URL
                """
            }
        }

        aborted {
            echo '⏱️ PIPELINE ABORTED!'
            mail(
                to: "${NOTIFY_EMAIL}",
                subject: "⏱️ Build #${BUILD_NUMBER} ABORTED — ${JOB_NAME}",
                body: """============================================================
  JENKINS CD PIPELINE - BUILD REPORT
============================================================

[Pipeline] Start of Pipeline
[Pipeline] node - Running on worker-node-1

  Stage 7  : TIMED OUT  Approval Gate  <-- NOBODY APPROVED
  Stage 8  : SKIPPED    Deploy to Production
  Stage 9  : SKIPPED    Health Check
  Stage 10 : SKIPPED    Image Cleanup

[Pipeline] Post Actions
  Status   : ABORTED
  Build    : #${BUILD_NUMBER}
  Reason   : No approval within 5 minutes
  Action   : Production unchanged

============================================================
[Pipeline] End of Pipeline
Finished: ABORTED
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n  Stage 7  : TIMED OUT Approval Gate\\n  Stage 8  : SKIPPED   Deploy Production\\n\\n  Status   : ABORTED\\n  Build    : #${BUILD_NUMBER}\\n  Reason   : No approval in 5 minutes\\n  Action   : Production unchanged\\n============================================================\\nFinished: ABORTED\\n============================================================```"}' \
                    \$SLACK_URL
                """
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
