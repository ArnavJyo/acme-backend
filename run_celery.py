#!/usr/bin/env python3
"""
Run script for Celery worker
"""
from celery_app import celery

if __name__ == '__main__':
    celery.worker_main(['worker', '--loglevel=info', '--pool=solo'])

