pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                echo '📥 Pulling latest code from GitHub...'
                checkout scm
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Running automated tests...'
                sh '''
                    cd $WORKSPACE
                    python3 -m pytest test_app.py -v
                '''
            }
        }

        stage('Deploy Flask App') {
            steps {
                echo '🚀 Deploying Flask...'
                sh '''
                    pkill -f "python3 app.py" || true
                    sleep 2
                    cd $WORKSPACE
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
                    curl -s http://localhost:5000/ | python3 -m json.tool
                    curl -s http://localhost:5000/health | python3 -m json.tool
                    echo "✅ Flask is LIVE on port 5000!"
                '''
            }
        }
    }

    post {
        success { echo '🎉 Flask deployed and all tests passed!' }
        failure {
            sh 'cat $WORKSPACE/flask.log || true'
            echo '❌ Build failed — check logs above!'
        }
    }
}
