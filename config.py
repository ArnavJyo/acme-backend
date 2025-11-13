import os
from dotenv import load_dotenv

load_dotenv()
print(os.environ.get('SECRET_KEY'))
class Config:
    """Application configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') 
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CLOUDAMQP_URL') 
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'rpc://'
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'csv'}
    
    # Pagination
    PRODUCTS_PER_PAGE = 50

