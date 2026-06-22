from flask import Flask, jsonify
import os

app = Flask(__name__)

# Read environment — defaults to 'production'
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')
VERSION      = os.environ.get('APP_VERSION', '1.0')

@app.route('/')
def home():
    return jsonify({
        "message"    : "Hello from Flask!",
        "status"     : "running",
        "environment": ENVIRONMENT,
        "version"    : VERSION,
        "deployed_by": "Jenkins CI/CD"
    })

@app.route('/health')
def health():
    return jsonify({
        "status"     : "healthy",
        "environment": ENVIRONMENT
    }), 200

@app.route('/add/<int:a>/<int:b>')
def add(a, b):
    return jsonify({"result": a + b})

@app.route('/version')
def version():
    return jsonify({
        "version"    : VERSION,
        "environment": ENVIRONMENT,
        "build"      : os.environ.get('BUILD_NUMBER', 'local')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
