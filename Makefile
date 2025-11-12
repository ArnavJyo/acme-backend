.PHONY: install run worker test clean

install:
	pip install -r requirements.txt

run:
	python run.py

worker:
	celery -A celery_app worker --loglevel=info

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf uploads/*.csv

