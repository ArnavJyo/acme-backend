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
    Process CSV file import asynchronously.
    Efficient, chunked, batched, and progress-tracked version.
    """
    app = create_flask_app()
    with app.app_context():
        try:
            job = ImportJob.query.filter_by(task_id=task_id).first()
            if not job:
                return {'status': 'error', 'message': 'Job not found'}

            job.status = 'processing'
            job.progress = 0
            job.processed_records = 0
            db.session.commit()

            # --- Configuration ---
            chunk_size = 10000               # Rows per pandas chunk
            commit_interval = 500             # Commit product writes every 500
            progress_update_interval = 100    # Update job progress every 100

            total_processed = total_created = total_updated = 0

            # --- Count total rows efficiently ---
            try:
                total_rows = sum(len(chunk) for chunk in pd.read_csv(filepath, chunksize=chunk_size, dtype=str))
            except Exception:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    next(f, None)  # Skip header
                    total_rows = sum(1 for _ in f)

            if total_rows <= 0:
                job.status = 'failed'
                job.error_message = 'CSV file is empty or invalid'
                db.session.commit()
                return {'status': 'error', 'message': 'Empty or invalid CSV'}

            job.total_records = total_rows
            db.session.commit()
            print(f" Starting import: {total_rows} total rows")

            # --- Process CSV in chunks ---
            for chunk_num, chunk in enumerate(pd.read_csv(filepath, chunksize=chunk_size, dtype=str)):
                products_to_create, products_to_update = [], []

                for _, row in chunk.iterrows():
                    try:
                        sku = str(row.get('sku', '')).strip().lower()
                        if not sku:
                            continue

                        name = str(row.get('name', '')).strip()
                        description = str(row.get('description', '')).strip()

                        existing_product = Product.query.filter(
                            db.func.lower(Product.sku) == sku
                        ).first()

                        if existing_product:
                            existing_product.name = name
                            existing_product.description = description
                            existing_product.updated_at = datetime.utcnow()
                            products_to_update.append(existing_product)
                            total_updated += 1
                        else:
                            products_to_create.append(Product(
                                sku=sku,
                                name=name,
                                description=description,
                                active=True
                            ))
                            total_created += 1

                        total_processed += 1

                        # --- Update progress every 100 records ---
                        if total_processed % progress_update_interval == 0:
                            progress = int((total_processed / total_rows) * 100)
                            job.progress = progress
                            job.processed_records = total_processed
                            db.session.commit()

                            self.update_state(
                                state='PROGRESS',
                                meta={
                                    'current': total_processed,
                                    'total': total_rows,
                                    'progress': progress,
                                    'status': f'Processing {total_processed}/{total_rows}'
                                }
                            )

                        # --- Commit DB writes every 500 records ---
                        if total_processed % commit_interval == 0:
                            if products_to_create:
                                db.session.bulk_save_objects(products_to_create)
                                products_to_create.clear()

                            if products_to_update:
                                for prod in products_to_update:
                                    db.session.merge(prod)
                                products_to_update.clear()

                            db.session.commit()
                            print(f" Committed {total_processed}/{total_rows} records")

                    except Exception as e:
                        print(f" Error processing row: {e}")
                        continue

                # --- Commit any remaining records in this chunk ---
                if products_to_create:
                    db.session.bulk_save_objects(products_to_create)
                if products_to_update:
                    for prod in products_to_update:
                        db.session.merge(prod)
                db.session.commit()

                # --- Update progress after each chunk ---
                progress = int((total_processed / total_rows) * 100)
                job.progress = progress
                job.processed_records = total_processed
                db.session.commit()

                print(f" Finished chunk {chunk_num + 1}, progress: {progress}%")

            # --- Mark job as complete ---
            job.status = 'completed'
            job.progress = 100
            job.processed_records = total_processed
            db.session.commit()

            # --- Cleanup ---
            try:
                os.remove(filepath)
            except Exception:
                pass

            print(f" Import completed: {total_processed} processed, {total_created} created, {total_updated} updated")

            return {
                'status': 'completed',
                'total_processed': total_processed,
                'total_created': total_created,
                'total_updated': total_updated
            }

        except Exception as e:
            error_msg = str(e)
            print(f"Import failed: {error_msg}")
            traceback.print_exc()

            job = ImportJob.query.filter_by(task_id=task_id).first()
            if job:
                job.status = 'failed'
                job.error_message = error_msg
                db.session.commit()

            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

            return {'status': 'error', 'message': error_msg}
