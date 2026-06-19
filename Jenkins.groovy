pipeline {
    agent any

    environment {
        APP_PORT    = '5000'
        VENV_DIR    = 'venv'
        APP_NAME    = 'flask-app'
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Pulling Flask app from GitHub...'
                checkout scm
            }
        }

        stage('Setup Python Environment') {
            steps {
                echo '🐍 Creating Python virtual environment...'
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    echo "✅ Dependencies installed!"
                    pip list
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Running automated tests...'
                sh '''
                    . venv/bin/activate
                    pytest test_app.py -v --tb=short
                '''
            }
        }

        stage('Deploy Flask App') {
            steps {
                echo '🚀 Deploying Flask application...'
                sh '''
                    # Kill any existing Flask process
                    pkill -f "python3 app.py" || true
                    sleep 2

                    # Start Flask in background
                    . venv/bin/activate
                    nohup python3 app.py > flask.log 2>&1 &
                    echo $! > flask.pid

                    sleep 3
                    echo "✅ Flask started with PID: $(cat flask.pid)"
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                echo '🌐 Verifying Flask is responding...'
                sh '''
                    sleep 2
                    curl -s http://localhost:5000/ | python3 -m json.tool
                    curl -s http://localhost:5000/health | python3 -m json.tool
                    echo "✅ Flask app is LIVE on port 5000!"
                '''
            }
        }
    }

    post {
        success {
            echo '🎉 Flask app deployed and all tests passed!'
        }
        failure {
            echo '❌ Build failed! Check test results or deployment logs.'
            sh 'cat flask.log || true'
        }
    }
}
