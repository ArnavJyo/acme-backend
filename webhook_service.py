import requests
import time
from models import Webhook
from flask import current_app

def trigger_webhook(webhook, event_type, payload):
    """
    Trigger a webhook with the given payload
    Returns response info or None if failed
    """
    if not webhook.enabled or webhook.event_type != event_type:
        return None
    
    try:
        start_time = time.time()
        response = requests.post(
            webhook.url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return {
            'success': response.status_code < 400,
            'status_code': response.status_code,
            'response_time_ms': round(response_time, 2),
            'response_text': response.text[:500] if response.text else ''
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': str(e),
            'status_code': None,
            'response_time_ms': None
        }

def trigger_webhooks_for_event(event_type, payload):
    """
    Trigger all enabled webhooks for a given event type
    """
    webhooks = Webhook.query.filter_by(
        event_type=event_type,
        enabled=True
    ).all()
    
    results = []
    for webhook in webhooks:
        result = trigger_webhook(webhook, event_type, payload)
        if result:
            result['webhook_id'] = webhook.id
            result['webhook_url'] = webhook.url
            results.append(result)
    
    return results

