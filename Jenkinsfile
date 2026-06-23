pipeline {
    agent any

    environment {
        IMAGE_NAME        = 'flask-jenkins-app'
        STAGING_CONTAINER = 'flask-staging'
        PROD_CONTAINER    = 'flask-production'
        STAGING_PORT      = '5001'
        PROD_PORT         = '5000'
        NOTIFY_EMAIL      = 'shivaguru1207@gmail.com'
        FAILED_STAGE      = 'None'
        FAILED_FILE       = 'None'
        ERROR_DETAILS     = 'None'
    }

    stages {

        stage('Checkout') {
            steps {
                echo '📥 Stage 1: Pulling latest code...'
                checkout scm
                script {
                    env.GIT_COMMIT_MSG = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    env.GIT_AUTHOR    = sh(script: 'git log -1 --pretty=%an', returnStdout: true).trim()
                    env.GIT_COMMIT_ID = sh(script: 'git log -1 --pretty=%h', returnStdout: true).trim()
                }
                echo "Commit: ${env.GIT_COMMIT_MSG}"
                echo "Author: ${env.GIT_AUTHOR}"
                echo "Hash:   ${env.GIT_COMMIT_ID}"
            }
            post {
                failure {
                    script {
                        env.FAILED_STAGE = 'Stage 1: Checkout'
                        env.FAILED_FILE  = 'Jenkinsfile / GitHub credentials'
                        env.ERROR_DETAILS = 'Could not clone repository. Check GitHub credentials or repo URL.'
                    }
                }
            }
        }

        stage('Code Quality') {
            steps {
                echo '🔍 Stage 2: Checking code quality...'
                script {
                    // Check app.py syntax
                    def appResult = sh(
                        script: 'python3 -m py_compile app.py 2>&1',
                        returnStdout: true,
                        returnStatus: false
                    )

                    // Check test_app.py syntax  
                    try {
                        sh 'python3 -m py_compile app.py 2>&1'
                        echo '✅ app.py syntax OK'
                    } catch(e) {
                        env.FAILED_FILE = 'app.py'
                        env.ERROR_DETAILS = sh(script: 'python3 -m py_compile app.py 2>&1 || true', returnStdout: true).trim()
                        error("Syntax error in app.py")
                    }

                    try {
                        sh 'python3 -m py_compile test_app.py 2>&1'
                        echo '✅ test_app.py syntax OK'
                    } catch(e) {
                        env.FAILED_FILE = 'test_app.py'
                        env.ERROR_DETAILS = sh(script: 'python3 -m py_compile test_app.py 2>&1 || true', returnStdout: true).trim()
                        error("Syntax error in test_app.py")
                    }
                }
            }
            post {
                failure {
                    script {
                        env.FAILED_STAGE = 'Stage 2: Code Quality'
                        if (env.FAILED_FILE == 'None') {
                            env.FAILED_FILE = 'app.py or test_app.py'
                        }
                    }
                }
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Stage 3: Running 5 automated tests...'
                script {
                    def testOutput = sh(
                        script: 'python3 -m pytest test_app.py -v --tb=short 2>&1',
                        returnStdout: true
                    )
                    echo testOutput

                    if (testOutput.contains('failed') || testOutput.contains('error')) {
                        // Extract which test failed
                        def failedTest = testOutput.findAll(/FAILED\s+\S+/).join(', ')
                        env.FAILED_STAGE   = 'Stage 3: Run Tests'
                        env.FAILED_FILE    = 'test_app.py'
                        env.ERROR_DETAILS  = failedTest ? "Failed tests: ${failedTest}" : "Test errors found — check console"
                        error("Tests failed!")
                    }
                    echo '✅ All 5 tests passed!'
                }
            }
            post {
                failure {
                    script {
                        env.FAILED_STAGE = 'Stage 3: Run Tests'
                        env.FAILED_FILE  = 'test_app.py — check which test failed'
                        if (env.ERROR_DETAILS == 'None') {
                            env.ERROR_DETAILS = sh(
                                script: 'python3 -m pytest test_app.py -v --tb=short 2>&1 | tail -20 || true',
                                returnStdout: true
                            ).trim()
                        }
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                echo '🐳 Stage 4: Building Docker image...'
                script {
                    try {
                        sh 'docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} .'
                        sh 'docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${IMAGE_NAME}:latest'
                        echo "✅ Image built: ${IMAGE_NAME}:${BUILD_NUMBER}"
                    } catch(e) {
                        env.FAILED_STAGE  = 'Stage 4: Build Docker Image'
                        env.FAILED_FILE   = 'Dockerfile'
                        env.ERROR_DETAILS = sh(
                            script: 'docker build -t test-check . 2>&1 | tail -10 || true',
                            returnStdout: true
                        ).trim()
                        error("Docker build failed!")
                    }
                }
            }
            post {
                failure {
                    script {
                        env.FAILED_STAGE = 'Stage 4: Build Docker Image'
                        env.FAILED_FILE  = 'Dockerfile'
                    }
                }
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
            post {
                failure {
                    script {
                        env.FAILED_STAGE  = 'Stage 5: Deploy to Staging'
                        env.FAILED_FILE   = 'Dockerfile / app.py'
                        env.ERROR_DETAILS = 'Docker container failed to start. Check Dockerfile CMD and app.py port.'
                    }
                }
            }
        }

        stage('Smoke Test Staging') {
            steps {
                echo '🔬 Stage 6: Smoke testing STAGING...'
                sh 'sleep 10'
                script {
                    // Test each endpoint and capture which one failed
                    def endpoints = [
                        [url: 'http://localhost:5001/health',  file: 'app.py → def health()'],
                        [url: 'http://localhost:5001/',         file: 'app.py → def home()'],
                        [url: 'http://localhost:5001/version',  file: 'app.py → def version()']
                    ]

                    endpoints.each { endpoint ->
                        def status = sh(
                            script: "curl -sf -o /dev/null -w '%{http_code}' ${endpoint.url} || echo '000'",
                            returnStdout: true
                        ).trim()

                        if (status == '200') {
                            echo "✅ ${endpoint.url} → HTTP ${status}"
                        } else {
                            env.FAILED_STAGE  = 'Stage 6: Smoke Test Staging'
                            env.FAILED_FILE   = endpoint.file
                            env.ERROR_DETAILS = "Endpoint ${endpoint.url} returned HTTP ${status} instead of 200"
                            error("Smoke test failed on ${endpoint.url}")
                        }
                    }
                    echo '✅ All staging smoke tests passed!'
                }
            }
            post {
                failure {
                    script {
                        env.FAILED_STAGE = 'Stage 6: Smoke Test Staging'
                        if (env.FAILED_FILE == 'None') {
                            env.FAILED_FILE   = 'app.py — endpoint not responding'
                            env.ERROR_DETAILS = 'Flask app not starting correctly in container. Check port in app.py'
                        }
                    }
                }
            }
        }

        stage('Approval Gate') {
            steps {
                echo '⏸️ Stage 7: Waiting for approval...'
                withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                    sh """
                        curl -s -X POST \
                        -H 'Content-type: application/json' \
                        -d '{"text":"```\\n[Pipeline] APPROVAL NEEDED\\n  Build  : #${BUILD_NUMBER}\\n  Commit : ${env.GIT_COMMIT_ID} - ${env.GIT_COMMIT_MSG}\\n  Author : ${env.GIT_AUTHOR}\\n  Staging: http://localhost:5001\\n  Action : Go to http://localhost:8080 to approve```"}' \
                        \$SLACK_URL
                    """
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
                    env.PREV_BUILD = prevBuild ? prevBuild.number.toString() : '0'
                    echo "Previous good build: #${env.PREV_BUILD}"
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
            post {
                failure {
                    script {
                        env.FAILED_STAGE  = 'Stage 8: Deploy to Production'
                        env.FAILED_FILE   = 'Dockerfile / app.py'
                        env.ERROR_DETAILS = 'Production container failed to start. Port conflict or image issue.'
                    }
                }
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

                    echo "Health check HTTP status: ${healthStatus}"

                    if (healthStatus == '200') {
                        echo '✅ Health check PASSED!'
                        sh 'curl -sf http://localhost:5000/       | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                    } else {
                        env.FAILED_STAGE  = 'Stage 9: Health Check'
                        env.FAILED_FILE   = 'app.py → check port, routes, and runtime errors'
                        env.ERROR_DETAILS = "Health check on http://localhost:5000/health returned HTTP ${healthStatus} instead of 200. App may have crashed at startup."

                        echo "❌ FAILED! Rolling back to build #${env.PREV_BUILD}..."
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
  Stage 4  : OK  Build Docker Image  flask-jenkins-app:${BUILD_NUMBER}
  Stage 5  : OK  Deploy to Staging   port 5001
  Stage 6  : OK  Smoke Test Staging
  Stage 7  : OK  Approval Gate       APPROVED by admin
  Stage 8  : OK  Deploy to Production port 5000
  Stage 9  : OK  Health Check        HTTP 200
  Stage 10 : OK  Image Cleanup

------------------------------------------------------------
  COMMIT DETAILS
------------------------------------------------------------
  Author : ${env.GIT_AUTHOR}
  Commit : ${env.GIT_COMMIT_ID}
  Message: ${env.GIT_COMMIT_MSG}

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
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  Stage 1  : OK  Checkout SCM\\n  Stage 2  : OK  Code Quality\\n  Stage 3  : OK  Run Tests (5/5)\\n  Stage 4  : OK  Docker Image :${BUILD_NUMBER}\\n  Stage 5  : OK  Deploy Staging\\n  Stage 6  : OK  Smoke Tests\\n  Stage 7  : OK  Approved\\n  Stage 8  : OK  Deploy Production\\n  Stage 9  : OK  Health Check HTTP 200\\n  Stage 10 : OK  Cleanup\\n\\n  Author : ${env.GIT_AUTHOR}\\n  Commit : ${env.GIT_COMMIT_ID}\\n  Msg    : ${env.GIT_COMMIT_MSG}\\n\\n  Status : SUCCESS\\n  Build  : #${BUILD_NUMBER}\\n  URL    : http://localhost:5000\\n============================================================\\nFinished: SUCCESS\\n============================================================```"}' \
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

------------------------------------------------------------
  FAILURE DETAILS
------------------------------------------------------------
  Failed Stage : ${env.FAILED_STAGE}
  Failed File  : ${env.FAILED_FILE}
  Error        : ${env.ERROR_DETAILS}

------------------------------------------------------------
  COMMIT THAT BROKE THE BUILD
------------------------------------------------------------
  Author  : ${env.GIT_AUTHOR}
  Commit  : ${env.GIT_COMMIT_ID}
  Message : ${env.GIT_COMMIT_MSG}

------------------------------------------------------------
  HOW TO FIX
------------------------------------------------------------
  1. Open file: ${env.FAILED_FILE}
  2. Fix the error: ${env.ERROR_DETAILS}
  3. Commit fix to GitHub
  4. Pipeline will auto-trigger and retry

  Full console log: ${BUILD_URL}console

------------------------------------------------------------
  ROLLBACK STATUS
------------------------------------------------------------
  Production is running previous build: #${env.PREV_BUILD}
  URL: http://localhost:5000

============================================================
[Pipeline] End of Pipeline
Finished: FAILURE
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  FAILED STAGE : ${env.FAILED_STAGE}\\n  FAILED FILE  : ${env.FAILED_FILE}\\n  ERROR        : ${env.ERROR_DETAILS}\\n\\n  COMMIT DETAILS\\n  Author  : ${env.GIT_AUTHOR}\\n  Commit  : ${env.GIT_COMMIT_ID}\\n  Message : ${env.GIT_COMMIT_MSG}\\n\\n  HOW TO FIX\\n  1. Open file : ${env.FAILED_FILE}\\n  2. Fix error : ${env.ERROR_DETAILS}\\n  3. Push fix to GitHub - pipeline auto-retries\\n\\n  ROLLBACK\\n  Production running build: #${env.PREV_BUILD}\\n  Logs: http://localhost:8080/job/flask-app-pipeline/${BUILD_NUMBER}/console\\n============================================================\\nFinished: FAILURE\\n============================================================```"}' \
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

------------------------------------------------------------
  COMMIT DETAILS
------------------------------------------------------------
  Author  : ${env.GIT_AUTHOR}
  Commit  : ${env.GIT_COMMIT_ID}
  Message : ${env.GIT_COMMIT_MSG}

------------------------------------------------------------
  STATUS
------------------------------------------------------------
  Nobody approved within 5 minutes
  Production unchanged - still running previous version

  View build: ${BUILD_URL}

============================================================
[Pipeline] End of Pipeline
Finished: ABORTED
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n  Stage 7  : TIMED OUT Approval Gate\\n  Stage 8  : SKIPPED   Deploy Production\\n\\n  Author  : ${env.GIT_AUTHOR}\\n  Commit  : ${env.GIT_COMMIT_ID}\\n  Message : ${env.GIT_COMMIT_MSG}\\n\\n  Status  : ABORTED\\n  Reason  : No approval in 5 minutes\\n  Action  : Production unchanged\\n============================================================\\nFinished: ABORTED\\n============================================================```"}' \
                    \$SLACK_URL
                """
            }
        }

        always {
            echo "📊 Build #${BUILD_NUMBER} — ${currentBuild.currentResult}"
        }
    }
}
