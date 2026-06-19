pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                echo '✅ Stage 1: Code checked out from GitHub'
            }
        }
        stage('Build') {
            steps {
                echo '🔨 Stage 2: Building the project...'
                sh 'echo "Build date: $(date)"'
                sh 'echo "Running on: $(hostname)"'
            }
        }
        stage('Test') {
            steps {
                echo '🧪 Stage 3: Running tests...'
                sh 'echo "All tests passed!"'
            }
        }
        stage('Deploy') {
            steps {
                echo '🚀 Stage 4: Deploying application...'
                sh 'echo "Deployed successfully at $(date)"'
            }
        }
    }
    post {
        success {
            echo '✅ Pipeline completed SUCCESSFULLY!'
        }
        failure {
            echo '❌ Pipeline FAILED! Check logs.'
        }
    }
}
