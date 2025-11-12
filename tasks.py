import os
import pandas as pd
from celery_app import celery
from models import db, Product, ImportJob
from flask import Flask
from datetime import datetime
import traceback

def create_flask_app():
    """Create Flask app context for Celery tasks"""
    from config import Config
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

@celery.task(bind=True, name='tasks.process_csv_import')
def process_csv_import(self, filepath, task_id):
    """
    Process CSV file import asynchronously
    Updates progress through task state
    """
    app = create_flask_app()
    
    with app.app_context():
        try:
            # Update job status to processing
            job = ImportJob.query.filter_by(task_id=task_id).first()
            if not job:
                return {'status': 'error', 'message': 'Job not found'}
            
            job.status = 'processing'
            job.progress = 0
            db.session.commit()
            
            # Read CSV in chunks for memory efficiency
            chunk_size = 10000
            total_processed = 0
            total_updated = 0
            total_created = 0
            
            # First pass: count total rows
            df_temp = pd.read_csv(filepath, nrows=1)
            total_rows = sum(1 for _ in open(filepath)) - 1  # Subtract header
            job.total_records = total_rows
            db.session.commit()
            
            # Process CSV in chunks
            for chunk_num, chunk in enumerate(pd.read_csv(filepath, chunksize=chunk_size, dtype=str)):
                products_to_create = []
                products_to_update = []
                
                for _, row in chunk.iterrows():
                    try:
                        # Extract data from CSV row
                        sku = str(row.get('sku', '')).strip().lower() if pd.notna(row.get('sku')) else None
                        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                        description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else ''
                        
                        if not sku:
                            continue  # Skip rows without SKU
                        
                        # Check if product exists (case-insensitive SKU)
                        existing_product = Product.query.filter(
                            db.func.lower(Product.sku) == sku.lower()
                        ).first()
                        
                        if existing_product:
                            # Update existing product
                            existing_product.name = name
                            existing_product.description = description
                            existing_product.updated_at = datetime.utcnow()
                            products_to_update.append(existing_product)
                            total_updated += 1
                        else:
                            # Create new product
                            new_product = Product(
                                sku=sku,
                                name=name,
                                description=description,
                                active=True
                            )
                            products_to_create.append(new_product)
                            total_created += 1
                        
                        total_processed += 1
                        
                    except Exception as e:
                        # Log error but continue processing
                        print(f"Error processing row: {e}")
                        continue
                
                # Bulk insert/update
                if products_to_create:
                    db.session.bulk_save_objects(products_to_create)
                
                if products_to_update:
                    for product in products_to_update:
                        db.session.merge(product)
                
                db.session.commit()
                
                # Update progress
                progress = int((total_processed / total_rows) * 100) if total_rows > 0 else 0
                job.progress = progress
                job.processed_records = total_processed
                db.session.commit()
                
                # Update task state
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': total_processed,
                        'total': total_rows,
                        'progress': progress,
                        'status': f'Processing... {total_processed}/{total_rows}'
                    }
                )
            
            # Mark job as completed
            job.status = 'completed'
            job.progress = 100
            job.processed_records = total_processed
            db.session.commit()
            
            # Clean up file
            try:
                os.remove(filepath)
            except:
                pass
            
            return {
                'status': 'completed',
                'total_processed': total_processed,
                'total_created': total_created,
                'total_updated': total_updated
            }
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"Import error: {error_msg}\n{error_trace}")
            
            # Update job status to failed
            job = ImportJob.query.filter_by(task_id=task_id).first()
            if job:
                job.status = 'failed'
                job.error_message = error_msg
                db.session.commit()
            
            # Clean up file
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
            
            return {
                'status': 'error',
                'message': error_msg
            }

