post {
        always {
            echo "📊 Build #${BUILD_NUMBER} status: ${currentBuild.currentResult}"
        }
        success {
            echo '🎉 PIPELINE COMPLETED SUCCESSFULLY!'

            mail to: "${NOTIFY_EMAIL}",
                 subject: "✅ Jenkins Build #${BUILD_NUMBER} PASSED — ${JOB_NAME}",
                 body: "Build SUCCESS!\n\nApp URL: http://localhost:5000\nView build: ${BUILD_URL}"

            sh '''curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"✅ SUCCESS: Flask Build PASSED! App is live on Port 5000!"}' \
                https://hooks.slack.com/services/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'''
        }
        failure {
            echo '❌ PIPELINE FAILED — check logs above!'

            mail to: "${NOTIFY_EMAIL}",
                 subject: "❌ Jenkins Build #${BUILD_NUMBER} FAILED — ${JOB_NAME}",
                 body: "Build FAILED!\n\nCheck logs:\n${BUILD_URL}console"

            sh '''curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"❌ FAILED: Flask Build BROKE! Check Jenkins logs immediately!"}' \
                https://hooks.slack.com/services/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'''
        }
    }
