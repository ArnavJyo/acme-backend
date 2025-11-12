from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config
from models import db
from routes import register_routes

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__, static_folder='static')
    app.config.from_object(Config)
    
    # Enable CORS for frontend
    CORS(app)
    
    # Initialize database
    db.init_app(app)
    
    # Register routes
    register_routes(app)
    
    # Serve frontend
    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')
    
    # Create upload directory
    import os
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

