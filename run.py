#!/usr/bin/env python3
"""
Run script for the Flask application
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        from models import db
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

