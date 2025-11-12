from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, func
from datetime import datetime

db = SQLAlchemy()

class Product(db.Model):
    """Product model"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Case-insensitive unique index on SKU
    __table_args__ = (
        Index('ix_products_sku_lower', func.lower(db.text('sku')), unique=True),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Product {self.sku}>'


class Webhook(db.Model):
    """Webhook configuration model"""
    __tablename__ = 'webhooks'
    
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)  # e.g., 'product.created', 'product.updated', 'product.deleted'
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    secret = db.Column(db.String(255))  # Optional webhook secret for signing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'event_type': self.event_type,
            'enabled': self.enabled,
            'secret': self.secret,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Webhook {self.url}>'


class ImportJob(db.Model):
    """Track CSV import jobs for progress tracking"""
    __tablename__ = 'import_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending', nullable=False)  # pending, processing, completed, failed
    progress = db.Column(db.Integer, default=0)  # 0-100
    total_records = db.Column(db.Integer, default=0)
    processed_records = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'filename': self.filename,
            'status': self.status,
            'progress': self.progress,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

