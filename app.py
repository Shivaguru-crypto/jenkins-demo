from flask import Flask, jsonify
import os

app = Flask(__name__)

ENVIRONMENT  = os.environ.get('ENVIRONMENT', 'production')
VERSION      = os.environ.get('APP_VERSION', '1.0')
BUILD_NUMBER = os.environ.get('BUILD_NUMBER', 'local')

@app.route('/')
def home():
    return jsonify({
        "message"     : "Hello from Flask!",
        "status"      : "running",
        "environment" : ENVIRONMENT,
        "version"     : VERSION,
        "build"       : BUILD_NUMBER,
        "deployed_by" : "Jenkins CI/CD"
    })

@app.route('/health')
def health():
    return jsonify({
        "status"      : "healthy",
        "environment" : ENVIRONMENT,
        "build"       : BUILD_NUMBER
    }), 200

@app.route('/add/<int:a>/<int:b>')
def add(a, b):
    return jsonify({"result": a + b})

@app.route('/version')
def version():
    return jsonify({
        "version"     : VERSION,
        "build"       : BUILD_NUMBER,
        "environment" : ENVIRONMENT
    })

@app.route('/simulate-error')
def simulate_error():
    # This route simulates a broken deployment for rollback testing
    return jsonify({"error": "Simulated failure!"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
