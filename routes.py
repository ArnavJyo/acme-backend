from flask import request, jsonify, send_file, Response, stream_with_context
from models import db, Product, Webhook, ImportJob
from tasks import process_csv_import
from webhook_service import trigger_webhook, trigger_webhooks_for_event
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime

def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def register_routes(app):
    """Register all application routes"""
    
    # ========== CSV Upload & Progress ==========
    
    @app.route('/api/upload', methods=['POST'])
    def upload_csv():
        """Upload CSV file and start async processing"""
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename, app.config['ALLOWED_EXTENSIONS']):
            return jsonify({'error': 'Invalid file type. Only CSV files are allowed.'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        task_id = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
        file.save(filepath)
        
        # Create import job record
        job = ImportJob(
            task_id=task_id,
            filename=filename,
            status='pending',
            progress=0
        )
        db.session.add(job)
        db.session.commit()
        
        # Start async task
        task = process_csv_import.delay(filepath, task_id)
        
        return jsonify({
            'task_id': task_id,
            'filename': filename,
            'status': 'pending'
        }), 202
    
    @app.route('/api/upload/progress/<task_id>', methods=['GET'])
    def get_upload_progress(task_id):
        """Get upload progress for a task (for polling)"""
        job = ImportJob.query.filter_by(task_id=task_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify(job.to_dict()), 200
    
    @app.route('/api/upload/progress/<task_id>/stream', methods=['GET'])
    def stream_upload_progress(task_id):
        """Server-Sent Events stream for real-time progress updates"""
        def generate():
            import time
            last_progress = -1
            last_status = None
            
            while True:
                try:
                    # Create a new session for each query to ensure fresh data
                    # This prevents SQLAlchemy from caching stale data
                    db.session.expire_all()
                    
                    # Query with fresh session state - use with_for_update to ensure we get latest data
                    job = ImportJob.query.filter_by(task_id=task_id).first()
                    
                    if not job:
                        yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                        break
                    
                    # Convert to dict to ensure we get current values
                    data = job.to_dict()
                    current_progress = data.get('progress', 0)
                    current_status = data.get('status', 'pending')
                    
                    # Only send update if progress or status changed (reduces unnecessary updates)
                    if current_progress != last_progress or current_status != last_status:
                        yield f"data: {json.dumps(data)}\n\n"
                        last_progress = current_progress
                        last_status = current_status
                    
                    # Check status after getting data
                    if current_status in ['completed', 'failed']:
                        # Send final update
                        yield f"data: {json.dumps(data)}\n\n"
                        break
                    
                    # Update more frequently (50ms) for smoother progress bar updates
                    time.sleep(0.05)
                    
                except Exception as e:
                    # Log error and send error message
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"SSE stream error: {e}\n{error_trace}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    time.sleep(1)  # Wait a bit before retrying
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
                'X-Content-Type-Options': 'nosniff'
            }
        )
    
    # ========== Product Management ==========
    
    @app.route('/api/products', methods=['GET'])
    def get_products():
        """Get products with filtering and pagination"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', app.config['PRODUCTS_PER_PAGE'], type=int)
        
        # Filtering
        query = Product.query
        
        sku_filter = request.args.get('sku')
        if sku_filter:
            query = query.filter(Product.sku.ilike(f'%{sku_filter}%'))
        
        name_filter = request.args.get('name')
        if name_filter:
            query = query.filter(Product.name.ilike(f'%{name_filter}%'))
        
        description_filter = request.args.get('description')
        if description_filter:
            query = query.filter(Product.description.ilike(f'%{description_filter}%'))
        
        active_filter = request.args.get('active')
        if active_filter is not None:
            active_bool = active_filter.lower() in ('true', '1', 'yes')
            query = query.filter(Product.active == active_bool)
        
        # Ordering
        sort_by = request.args.get('sort_by', 'id')
        sort_order = request.args.get('sort_order', 'asc')
        if hasattr(Product, sort_by):
            if sort_order == 'desc':
                query = query.order_by(getattr(Product, sort_by).desc())
            else:
                query = query.order_by(getattr(Product, sort_by))
        
        # Pagination
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        return jsonify({
            'products': [p.to_dict() for p in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }), 200
    
    @app.route('/api/products/<int:product_id>', methods=['GET'])
    def get_product(product_id):
        """Get a single product by ID"""
        product = Product.query.get_or_404(product_id)
        return jsonify(product.to_dict()), 200
    
    @app.route('/api/products', methods=['POST'])
    def create_product():
        """Create a new product"""
        data = request.get_json()
        
        if not data or 'sku' not in data:
            return jsonify({'error': 'SKU is required'}), 400
        
        # Check for duplicate SKU (case-insensitive)
        existing = Product.query.filter(
            db.func.lower(Product.sku) == data['sku'].lower()
        ).first()
        
        if existing:
            return jsonify({'error': 'Product with this SKU already exists'}), 400
        
        product = Product(
            sku=data['sku'],
            name=data.get('name', ''),
            description=data.get('description', ''),
            active=data.get('active', True)
        )
        
        db.session.add(product)
        db.session.commit()
        
        # Trigger webhook
        trigger_webhooks_for_event('product.created', {
            'event': 'product.created',
            'product': product.to_dict()
        })
        
        return jsonify(product.to_dict()), 201
    
    @app.route('/api/products/<int:product_id>', methods=['PUT'])
    def update_product(product_id):
        """Update an existing product"""
        product = Product.query.get_or_404(product_id)
        data = request.get_json()
        
        if 'sku' in data:
            # Check for duplicate SKU (case-insensitive, excluding current product)
            existing = Product.query.filter(
                db.func.lower(Product.sku) == data['sku'].lower(),
                Product.id != product_id
            ).first()
            
            if existing:
                return jsonify({'error': 'Product with this SKU already exists'}), 400
            
            product.sku = data['sku']
        
        if 'name' in data:
            product.name = data['name']
        
        if 'description' in data:
            product.description = data['description']
        
        if 'active' in data:
            product.active = data['active']
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Trigger webhook
        trigger_webhooks_for_event('product.updated', {
            'event': 'product.updated',
            'product': product.to_dict()
        })
        
        return jsonify(product.to_dict()), 200
    
    @app.route('/api/products/<int:product_id>', methods=['DELETE'])
    def delete_product(product_id):
        """Delete a product"""
        product = Product.query.get_or_404(product_id)
        product_data = product.to_dict()
        
        db.session.delete(product)
        db.session.commit()
        
        # Trigger webhook
        trigger_webhooks_for_event('product.deleted', {
            'event': 'product.deleted',
            'product': product_data
        })
        
        return jsonify({'message': 'Product deleted successfully'}), 200
    
    # ========== Bulk Delete ==========
    
    @app.route('/api/products/bulk-delete', methods=['DELETE'])
    def bulk_delete_products():
        """Delete all products"""
        try:
            count = Product.query.count()
            
            # Delete all products
            Product.query.delete()
            db.session.commit()
            
            # Trigger webhook
            trigger_webhooks_for_event('product.bulk_deleted', {
                'event': 'product.bulk_deleted',
                'count': count
            })
            
            return jsonify({
                'message': f'Successfully deleted {count} products',
                'count': count
            }), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    # ========== Webhook Management ==========
    
    @app.route('/api/webhooks', methods=['GET'])
    def get_webhooks():
        """Get all webhooks"""
        webhooks = Webhook.query.all()
        return jsonify([w.to_dict() for w in webhooks]), 200
    
    @app.route('/api/webhooks/<int:webhook_id>', methods=['GET'])
    def get_webhook(webhook_id):
        """Get a single webhook"""
        webhook = Webhook.query.get_or_404(webhook_id)
        return jsonify(webhook.to_dict()), 200
    
    @app.route('/api/webhooks', methods=['POST'])
    def create_webhook():
        """Create a new webhook"""
        data = request.get_json()
        
        if not data or 'url' not in data or 'event_type' not in data:
            return jsonify({'error': 'URL and event_type are required'}), 400
        
        webhook = Webhook(
            url=data['url'],
            event_type=data['event_type'],
            enabled=data.get('enabled', True),
            secret=data.get('secret')
        )
        
        db.session.add(webhook)
        db.session.commit()
        
        return jsonify(webhook.to_dict()), 201
    
    @app.route('/api/webhooks/<int:webhook_id>', methods=['PUT'])
    def update_webhook(webhook_id):
        """Update an existing webhook"""
        webhook = Webhook.query.get_or_404(webhook_id)
        data = request.get_json()
        
        if 'url' in data:
            webhook.url = data['url']
        
        if 'event_type' in data:
            webhook.event_type = data['event_type']
        
        if 'enabled' in data:
            webhook.enabled = data['enabled']
        
        if 'secret' in data:
            webhook.secret = data['secret']
        
        webhook.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(webhook.to_dict()), 200
    
    @app.route('/api/webhooks/<int:webhook_id>', methods=['DELETE'])
    def delete_webhook(webhook_id):
        """Delete a webhook"""
        webhook = Webhook.query.get_or_404(webhook_id)
        db.session.delete(webhook)
        db.session.commit()
        
        return jsonify({'message': 'Webhook deleted successfully'}), 200
    
    @app.route('/api/webhooks/<int:webhook_id>/test', methods=['POST'])
    def test_webhook(webhook_id):
        """Test a webhook with a sample payload"""
        webhook = Webhook.query.get_or_404(webhook_id)
        
        # Get custom payload from request or use default
        payload = request.get_json() or {
            'event': 'webhook.test',
            'message': 'This is a test webhook trigger',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        result = trigger_webhook(webhook, webhook.event_type, payload)
        
        if result:
            return jsonify({
                'webhook_id': webhook_id,
                'webhook_url': webhook.url,
                'test_result': result
            }), 200
        else:
            return jsonify({
                'error': 'Webhook is disabled or event type mismatch'
            }), 400
    
    # ========== Health Check ==========
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({'status': 'healthy'}), 200

