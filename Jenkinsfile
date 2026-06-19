pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Pulling latest code from GitHub...'
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                echo '🐍 Setting up Python...'
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install flask pytest
                    echo "✅ Dependencies installed!"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Running automated tests...'
                sh '''
                    . venv/bin/activate
                    pytest test_app.py -v
                '''
            }
        }

        stage('Deploy Flask App') {
            steps {
                echo '🚀 Deploying Flask...'
                sh '''
                    pkill -f "python3 app.py" || true
                    sleep 2
                    . venv/bin/activate
                    nohup python3 app.py > flask.log 2>&1 &
                    echo $! > flask.pid
                    sleep 3
                    echo "✅ Flask PID: $(cat flask.pid)"
                '''
            }
        }

        stage('Verify') {
            steps {
                echo '🌐 Verifying Flask is live...'
                sh '''
                    sleep 2
                    curl -s http://localhost:5000/
                    curl -s http://localhost:5000/health
                    echo "✅ Flask is LIVE!"
                '''
            }
        }
    }

    post {
        success { echo '🎉 Flask deployed successfully!' }
        failure {
            sh 'cat flask.log || true'
            echo '❌ Build failed!'
        }
    }
}
