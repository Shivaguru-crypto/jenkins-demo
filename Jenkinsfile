pipeline {
    agent any

    environment {
        IMAGE_NAME        = 'flask-jenkins-app'
        STAGING_CONTAINER = 'flask-staging'
        PROD_CONTAINER    = 'flask-production'
        STAGING_PORT      = '5001'
        PROD_PORT         = '5000'
        NOTIFY_EMAIL      = 'shivaguru1207@gmail.com'
        FAILED_STAGE      = 'Unknown'
        FAILED_FILE       = 'Unknown'
        ERROR_DETAILS     = 'Check console for details'
        PREV_BUILD        = '0'
        GIT_AUTHOR        = 'Unknown'
        GIT_COMMIT_ID     = 'Unknown'
        GIT_COMMIT_MSG    = 'Unknown'
    }

    stages {

        stage('Checkout') {
            steps {
                script {
                    try {
                        echo '📥 Stage 1: Pulling latest code...'
                        checkout scm
                        env.GIT_COMMIT_MSG = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                        env.GIT_AUTHOR    = sh(script: 'git log -1 --pretty=%an', returnStdout: true).trim()
                        env.GIT_COMMIT_ID = sh(script: 'git log -1 --pretty=%h',  returnStdout: true).trim()
                        echo "Author : ${env.GIT_AUTHOR}"
                        echo "Commit : ${env.GIT_COMMIT_ID}"
                        echo "Message: ${env.GIT_COMMIT_MSG}"
                    } catch(e) {
                        env.FAILED_STAGE  = 'Stage 1: Checkout'
                        env.FAILED_FILE   = 'Jenkinsfile or GitHub credentials'
                        env.ERROR_DETAILS = "Cannot clone repo. Check GitHub credentials. Error: ${e.getMessage()}"
                        error(env.ERROR_DETAILS)
                    }
                }
            }
        }

        stage('Code Quality') {
            steps {
                script {
                    echo '🔍 Stage 2: Checking code quality...'

                    // Check app.py
                    def appError = sh(
                        script: 'python3 -m py_compile app.py 2>&1; echo EXIT:$?',
                        returnStdout: true
                    ).trim()

                    if (appError.contains('EXIT:1') || appError.contains('SyntaxError') || appError.contains('Error')) {
                        env.FAILED_STAGE  = 'Stage 2: Code Quality'
                        env.FAILED_FILE   = 'app.py'
                        env.ERROR_DETAILS = appError.replace('EXIT:1','').replace('EXIT:0','').trim()
                        error("Syntax error in app.py: ${env.ERROR_DETAILS}")
                    }
                    echo '✅ app.py syntax OK'

                    // Check test_app.py
                    def testError = sh(
                        script: 'python3 -m py_compile test_app.py 2>&1; echo EXIT:$?',
                        returnStdout: true
                    ).trim()

                    if (testError.contains('EXIT:1') || testError.contains('SyntaxError') || testError.contains('Error')) {
                        env.FAILED_STAGE  = 'Stage 2: Code Quality'
                        env.FAILED_FILE   = 'test_app.py'
                        env.ERROR_DETAILS = testError.replace('EXIT:1','').replace('EXIT:0','').trim()
                        error("Syntax error in test_app.py: ${env.ERROR_DETAILS}")
                    }
                    echo '✅ test_app.py syntax OK'
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    echo '🧪 Stage 3: Running 5 automated tests...'
                    def testOutput = sh(
                        script: 'python3 -m pytest test_app.py -v --tb=short 2>&1',
                        returnStdout: true
                    ).trim()
                    echo testOutput

                    // Extract failed test name
                    def failedTests = testOutput.findAll(/FAILED\s+[\w:]+/).collect { it.trim() }
                    def errorLines  = testOutput.findAll(/AssertionError.*|assert.*/).collect { it.trim() }

                    if (testOutput.contains(' failed') || testOutput.contains('ERROR')) {
                        env.FAILED_STAGE  = 'Stage 3: Run Tests'
                        env.FAILED_FILE   = "test_app.py"
                        env.ERROR_DETAILS = failedTests ? "Failed: ${failedTests.join(', ')}" : "Test errors — see console"
                        if (errorLines) {
                            env.ERROR_DETAILS = env.ERROR_DETAILS + " | " + errorLines.take(2).join(' | ')
                        }
                        error("Tests failed! ${env.ERROR_DETAILS}")
                    }
                    echo '✅ All 5 tests passed!'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo '🐳 Stage 4: Building Docker image...'
                    def buildOutput = sh(
                        script: "docker build -t ${env.IMAGE_NAME}:${BUILD_NUMBER} . 2>&1",
                        returnStdout: true
                    ).trim()
                    echo buildOutput

                    if (buildOutput.contains('ERROR') || buildOutput.contains('error')) {
                        // Extract the actual error line
                        def errorLine = buildOutput.readLines().findAll {
                            it.contains('ERROR') || it.contains('error')
                        }.take(3).join(' | ')

                        env.FAILED_STAGE  = 'Stage 4: Build Docker Image'
                        env.FAILED_FILE   = 'Dockerfile'
                        env.ERROR_DETAILS = errorLine ?: 'Docker build failed — check Dockerfile'
                        error("Docker build failed!")
                    }
                    sh "docker tag ${env.IMAGE_NAME}:${BUILD_NUMBER} ${env.IMAGE_NAME}:latest"
                    echo "✅ Image built: ${env.IMAGE_NAME}:${BUILD_NUMBER}"
                }
            }
        }

        stage('Deploy to Staging') {
            steps {
                script {
                    echo '🔶 Stage 5: Deploying to STAGING...'
                    sh 'docker stop  flask-staging || true'
                    sh 'docker rm    flask-staging || true'
                    sh 'sleep 2'
                    def runOutput = sh(
                        script: """
                            docker run -d \
                                --name flask-staging \
                                -p 5001:5000 \
                                -e ENVIRONMENT=staging \
                                -e APP_VERSION=${BUILD_NUMBER} \
                                -e BUILD_NUMBER=${BUILD_NUMBER} \
                                --restart unless-stopped \
                                flask-jenkins-app:latest 2>&1
                        """,
                        returnStdout: true
                    ).trim()

                    if (runOutput.contains('Error') || runOutput.contains('failed')) {
                        env.FAILED_STAGE  = 'Stage 5: Deploy to Staging'
                        env.FAILED_FILE   = 'Dockerfile → CMD line / app.py → port'
                        env.ERROR_DETAILS = runOutput
                        error("Staging container failed to start!")
                    }
                    sh 'docker ps | grep flask-staging'
                    echo '✅ Staging LIVE on port 5001'
                }
            }
        }

        stage('Smoke Test Staging') {
            steps {
                script {
                    echo '🔬 Stage 6: Smoke testing STAGING...'
                    sh 'sleep 10'

                    def endpoints = [
                        [url: 'http://localhost:5001/health',  file: 'app.py → def health()',  name: '/health'],
                        [url: 'http://localhost:5001/',         file: 'app.py → def home()',    name: '/'],
                        [url: 'http://localhost:5001/version',  file: 'app.py → def version()', name: '/version']
                    ]

                    endpoints.each { endpoint ->
                        def status = sh(
                            script: "curl -sf -o /dev/null -w '%{http_code}' ${endpoint.url} 2>&1 || echo '000'",
                            returnStdout: true
                        ).trim()

                        if (status == '200') {
                            echo "✅ ${endpoint.name} → HTTP ${status}"
                        } else {
                            env.FAILED_STAGE  = 'Stage 6: Smoke Test Staging'
                            env.FAILED_FILE   = endpoint.file
                            env.ERROR_DETAILS = "Endpoint ${endpoint.url} returned HTTP ${status} instead of 200. Check if Flask app started correctly and port is 5000 in app.py"
                            error("Smoke test FAILED on ${endpoint.url} — HTTP ${status}")
                        }
                    }
                    echo '✅ All staging smoke tests passed!'
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
                        -d '{"text":"```\\n[Pipeline] APPROVAL NEEDED\\n  Build   : #${BUILD_NUMBER}\\n  Author  : ${env.GIT_AUTHOR}\\n  Commit  : ${env.GIT_COMMIT_ID}\\n  Message : ${env.GIT_COMMIT_MSG}\\n  Staging : http://localhost:5001\\n  Action  : Go to http://localhost:8080 to approve```"}' \
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
                script {
                    echo '🚀 Stage 8: Deploying to PRODUCTION...'

                    // Save previous build for rollback BEFORE deploying
                    def prevBuild = currentBuild.previousSuccessfulBuild
                    env.PREV_BUILD = prevBuild ? prevBuild.number.toString() : '0'
                    echo "Previous good build: #${env.PREV_BUILD}"

                    sh 'docker stop  flask-production || true'
                    sh 'docker rm    flask-production || true'
                    sh 'sleep 2'
                    sh """
                        docker run -d \
                            --name flask-production \
                            -p 5000:5000 \
                            -e ENVIRONMENT=production \
                            -e APP_VERSION=${BUILD_NUMBER} \
                            -e BUILD_NUMBER=${BUILD_NUMBER} \
                            --restart unless-stopped \
                            flask-jenkins-app:latest
                    """
                    sh 'docker ps | grep flask-production'
                    echo '✅ Production LIVE on port 5000'
                }
            }
        }

        stage('Health Check + Auto Rollback') {
            steps {
                script {
                    echo '🌐 Stage 9: Health check with auto-rollback...'
                    sh 'sleep 5'

                    def healthStatus = sh(
                        script: 'curl -sf -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>&1 || echo "000"',
                        returnStdout: true
                    ).trim()

                    echo "Health check HTTP status: ${healthStatus}"

                    if (healthStatus == '200') {
                        echo '✅ Health check PASSED!'
                        sh 'curl -sf http://localhost:5000/       | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/health | python3 -m json.tool'
                        sh 'curl -sf http://localhost:5000/version | python3 -m json.tool'
                    } else {
                        env.FAILED_STAGE  = 'Stage 9: Health Check + Auto Rollback'
                        env.FAILED_FILE   = 'app.py → check: wrong port number, syntax error at runtime, missing route'
                        env.ERROR_DETAILS = "http://localhost:5000/health returned HTTP ${healthStatus}. App crashed on startup. Most likely cause: wrong port in app.py (should be 5000 not 9999) OR runtime import error"

                        echo "❌ HEALTH CHECK FAILED — Status: ${healthStatus}"
                        echo "🔄 TRIGGERING AUTO ROLLBACK to build #${env.PREV_BUILD}..."

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
                            echo "✅ ROLLED BACK to build #${env.PREV_BUILD} successfully!"

                            // Immediate rollback Slack alert
                            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                                sh """
                                    curl -s -X POST \
                                    -H 'Content-type: application/json' \
                                    -d '{"text":"```\\n[Pipeline] AUTO ROLLBACK TRIGGERED\\n============================================================\\n  Failed Build : #${BUILD_NUMBER}\\n  Rolled Back  : to #${env.PREV_BUILD}\\n  Failed File  : app.py\\n  Error        : Health check HTTP ${healthStatus}\\n  Commit       : ${env.GIT_COMMIT_ID} by ${env.GIT_AUTHOR}\\n  Message      : ${env.GIT_COMMIT_MSG}\\n\\n  HOW TO FIX\\n  1. Open app.py\\n  2. Check last line - port must be 5000\\n  3. Check all routes return correct response\\n  4. Push fix - pipeline auto-retries\\n============================================================\\nFinished: ROLLBACK COMPLETE```"}' \
                                    \$SLACK_URL
                                """
                            }
                        } else {
                            echo "⚠️ No previous build to rollback to!"
                        }
                        error("Production health check failed! Rolled back to #${env.PREV_BUILD}")
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
  Stage 4  : OK  Build Docker Image  :${BUILD_NUMBER}
  Stage 5  : OK  Deploy to Staging   port 5001
  Stage 6  : OK  Smoke Test Staging
  Stage 7  : OK  Approval Gate       APPROVED
  Stage 8  : OK  Deploy to Production port 5000
  Stage 9  : OK  Health Check        HTTP 200
  Stage 10 : OK  Image Cleanup

------------------------------------------------------------
  COMMIT DETAILS
------------------------------------------------------------
  Author  : ${env.GIT_AUTHOR}
  Commit  : ${env.GIT_COMMIT_ID}
  Message : ${env.GIT_COMMIT_MSG}

------------------------------------------------------------
  LIVE ENDPOINTS
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
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  Stage 1  : OK  Checkout\\n  Stage 2  : OK  Code Quality\\n  Stage 3  : OK  Tests (5/5)\\n  Stage 4  : OK  Docker :${BUILD_NUMBER}\\n  Stage 5  : OK  Staging port 5001\\n  Stage 6  : OK  Smoke Tests\\n  Stage 7  : OK  Approved\\n  Stage 8  : OK  Production port 5000\\n  Stage 9  : OK  Health HTTP 200\\n  Stage 10 : OK  Cleanup\\n\\n  Author  : ${env.GIT_AUTHOR}\\n  Commit  : ${env.GIT_COMMIT_ID}\\n  Message : ${env.GIT_COMMIT_MSG}\\n\\n  Status  : SUCCESS\\n  Build   : #${BUILD_NUMBER}\\n  URL     : http://localhost:5000\\n============================================================\\nFinished: SUCCESS\\n============================================================```"}' \
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
  ❌ FAILURE DETAILS
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
  1. Open file : ${env.FAILED_FILE}
  2. Fix error : ${env.ERROR_DETAILS}
  3. Commit fix to GitHub
  4. Pipeline will auto-trigger and retry

  Full console: ${BUILD_URL}console

------------------------------------------------------------
  ROLLBACK STATUS
------------------------------------------------------------
  Production running previous build: #${env.PREV_BUILD}
  Production URL: http://localhost:5000

============================================================
[Pipeline] End of Pipeline
Finished: FAILURE
============================================================"""
            )
            withCredentials([string(credentialsId: 'slack-webhook-url', variable: 'SLACK_URL')]) {
                sh """
                    curl -s -X POST \
                    -H 'Content-type: application/json' \
                    -d '{"text":"```\\n============================================================\\n  JENKINS CD PIPELINE - BUILD REPORT\\n============================================================\\n[Pipeline] node - Running on worker-node-1\\n\\n  FAILED STAGE : ${env.FAILED_STAGE}\\n  FAILED FILE  : ${env.FAILED_FILE}\\n  ERROR        : ${env.ERROR_DETAILS}\\n\\n  COMMIT THAT BROKE THE BUILD\\n  Author  : ${env.GIT_AUTHOR}\\n  Commit  : ${env.GIT_COMMIT_ID}\\n  Message : ${env.GIT_COMMIT_MSG}\\n\\n  HOW TO FIX\\n  1. Open  : ${env.FAILED_FILE}\\n  2. Fix   : ${env.ERROR_DETAILS}\\n  3. Push fix - pipeline auto-retries\\n\\n  ROLLBACK\\n  Production running build: #${env.PREV_BUILD}\\n  Logs: http://localhost:8080/job/flask-app-pipeline/${BUILD_NUMBER}/console\\n============================================================\\nFinished: FAILURE\\n============================================================```"}' \
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
  Production unchanged - running previous version

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
