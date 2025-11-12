# Acme Product Importer Backend

A scalable Flask-based backend application for importing and managing products from CSV files. Designed to handle large datasets (up to 500,000 records) with real-time progress tracking, webhook support, and a complete product management system.

## Features

### STORY 1 - CSV File Upload
- Upload large CSV files (up to 500,000 products) through the web UI
- Real-time progress tracking with Server-Sent Events (SSE)
- Automatic duplicate handling (case-insensitive SKU matching)
- Async processing with Celery for optimal performance
- Visual progress indicators (progress bar, percentage, status messages)

### STORY 2 - Product Management
- Full CRUD operations (Create, Read, Update, Delete)
- Advanced filtering by SKU, name, description, and active status
- Paginated product listings
- Inline editing with modal forms
- Clean, minimalist UI

### STORY 3 - Bulk Delete
- Delete all products with confirmation dialog
- Success/failure notifications
- Webhook triggers for bulk operations

### STORY 4 - Webhook Management
- Configure multiple webhooks through UI
- Support for different event types (product.created, product.updated, product.deleted, product.bulk_deleted)
- Enable/disable webhooks
- Test webhooks with response code and timing information
- Webhook secret support for signing

## Tech Stack

- **Backend Framework**: Flask 3.0.0
- **Database**: Supabase PostgreSQL (via SQLAlchemy)
- **Message Queue**: CloudAMQP (RabbitMQ)
- **Async Tasks**: Celery 5.3.4
- **Frontend**: Vanilla HTML/CSS/JavaScript

## Prerequisites

- Python 3.8+
- PostgreSQL database (Supabase or local)
- CloudAMQP account (or local RabbitMQ instance)
- pip (Python package manager)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd acme-backend
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set the following:
   ```env
   # Database Configuration (Supabase PostgreSQL)
   DATABASE_URL=postgresql://user:password@host:port/database
   
   # CloudAMQP Configuration
   CLOUDAMQP_URL=amqp://user:password@host:port/vhost
   
   # Flask Configuration
   FLASK_ENV=development
   FLASK_DEBUG=True
   SECRET_KEY=your-secret-key-here
   
   # Celery Configuration
   CELERY_BROKER_URL=amqp://user:password@host:port/vhost
   CELERY_RESULT_BACKEND=rpc://
   ```

## Running the Application

### 1. Start the Flask Application

```bash
python run.py
```

Or using gunicorn for production:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:create_app()
```

The application will be available at `http://localhost:5000`

### 2. Start the Celery Worker

In a separate terminal:
```bash
celery -A celery_app worker --loglevel=info
```

Or using the run script:
```bash
python run_celery.py
```

## Database Setup

The application will automatically create the necessary tables on first run. The database models include:

- **products**: Stores product information (SKU, name, description, active status)
- **webhooks**: Stores webhook configurations
- **import_jobs**: Tracks CSV import progress

## API Endpoints

### CSV Upload
- `POST /api/upload` - Upload CSV file
- `GET /api/upload/progress/<task_id>` - Get upload progress (polling)
- `GET /api/upload/progress/<task_id>/stream` - Stream upload progress (SSE)

### Products
- `GET /api/products` - List products (with filtering and pagination)
- `GET /api/products/<id>` - Get single product
- `POST /api/products` - Create product
- `PUT /api/products/<id>` - Update product
- `DELETE /api/products/<id>` - Delete product
- `DELETE /api/products/bulk-delete` - Delete all products

### Webhooks
- `GET /api/webhooks` - List all webhooks
- `GET /api/webhooks/<id>` - Get single webhook
- `POST /api/webhooks` - Create webhook
- `PUT /api/webhooks/<id>` - Update webhook
- `DELETE /api/webhooks/<id>` - Delete webhook
- `POST /api/webhooks/<id>/test` - Test webhook

### Health
- `GET /api/health` - Health check endpoint

## CSV File Format

The CSV file should have the following columns:
- `sku` (required): Product SKU (case-insensitive, must be unique)
- `name`: Product name
- `description`: Product description

Example CSV:
```csv
sku,name,description
ABC123,Product 1,Description 1
XYZ789,Product 2,Description 2
```

## Webhook Events

The following events trigger webhooks:
- `product.created` - When a product is created
- `product.updated` - When a product is updated
- `product.deleted` - When a product is deleted
- `product.bulk_deleted` - When all products are deleted

Webhook payload format:
```json
{
  "event": "product.created",
  "product": {
    "id": 1,
    "sku": "ABC123",
    "name": "Product Name",
    "description": "Description",
    "active": true,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00"
  }
}
```

## Performance Optimizations

1. **Chunked CSV Processing**: Large CSV files are processed in chunks (10,000 records at a time) to manage memory efficiently
2. **Bulk Database Operations**: Uses SQLAlchemy bulk operations for faster inserts/updates
3. **Async Processing**: CSV imports run asynchronously using Celery, keeping the API responsive
4. **Database Indexing**: SKU field is indexed for fast lookups and case-insensitive uniqueness
5. **Connection Pooling**: SQLAlchemy connection pooling configured for optimal database performance

## Development

### Project Structure
```
acme-backend/
├── app.py                 # Flask application factory
├── config.py              # Configuration settings
├── models.py              # Database models
├── routes.py              # API routes
├── tasks.py               # Celery async tasks
├── celery_app.py          # Celery configuration
├── webhook_service.py     # Webhook triggering service
├── run.py                 # Flask run script
├── run_celery.py          # Celery worker script
├── requirements.txt       # Python dependencies
├── static/
│   └── index.html         # Frontend UI
└── uploads/               # CSV upload directory (created automatically)
```

## Troubleshooting

### Celery Worker Not Processing Tasks
- Ensure CloudAMQP/RabbitMQ is running and accessible
- Check that `CELERY_BROKER_URL` is correctly set in `.env`
- Verify the worker is connected: `celery -A celery_app inspect active`

### Database Connection Issues
- Verify `DATABASE_URL` is correct in `.env`
- Ensure PostgreSQL is running and accessible
- Check network connectivity to Supabase if using cloud database

### CSV Import Fails
- Check file format matches expected CSV structure
- Ensure SKU column exists and is not empty
- Review Celery worker logs for detailed error messages
- Check available disk space in `uploads/` directory

## License

This project is part of the Acme Inc. product importer system.
