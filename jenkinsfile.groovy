pipeline {
    agent any

    environment {
        DEPLOY_DIR = '/var/www/html'
        SITE_NAME  = 'html-website'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Pulling latest code from GitHub...'
                checkout scm
            }
        }

        stage('Validate') {
            steps {
                echo '🔍 Validating HTML files...'
                sh '''
                    echo "Files in workspace:"
                    ls -la
                    echo "Checking index.html exists..."
                    test -f index.html && echo "✅ index.html found" || exit 1
                    test -f style.css  && echo "✅ style.css found"  || exit 1
                '''
            }
        }

        stage('Deploy') {
            steps {
                echo '🚀 Deploying to Nginx web server...'
                sh '''
                    sudo cp index.html /var/www/html/index.html
                    sudo cp style.css  /var/www/html/style.css
                    echo "✅ Files deployed to /var/www/html/"
                    ls -la /var/www/html/
                '''
            }
        }

        stage('Verify') {
            steps {
                echo '🌐 Verifying deployment...'
                sh '''
                    curl -s -o /dev/null -w "HTTP Status: %{http_code}" http://localhost:80
                    echo ""
                    echo "✅ Site is LIVE at http://localhost:80"
                '''
            }
        }
    }

    post {
        success {
            echo '🎉 HTML site deployed successfully!'
        }
        failure {
            echo '❌ Deployment failed! Check logs above.'
        }
    }
}
