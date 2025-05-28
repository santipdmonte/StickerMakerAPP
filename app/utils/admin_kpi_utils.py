import time
from datetime import datetime, timedelta
from .dynamodb_utils import get_dynamodb_resource, USER_TABLE, TRANSACTION_TABLE, ADMIN_REQUEST_TABLE

def get_total_users():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    response = table.scan(Select='COUNT')
    return response.get('Count', 0)

def get_new_users(days=7):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    since = int(time.time()) - days * 86400
    response = table.scan(
        FilterExpression='#created_at >= :since',
        ExpressionAttributeNames={'#created_at': 'created_at'},
        ExpressionAttributeValues={':since': since},
        Select='COUNT'
    )
    return response.get('Count', 0)

def get_active_users(days=1):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    since = int(time.time()) - days * 86400
    response = table.scan(
        FilterExpression='#last_login >= :since',
        ExpressionAttributeNames={'#last_login': 'last_login'},
        ExpressionAttributeValues={':since': since},
        Select='COUNT'
    )
    return response.get('Count', 0)

def get_total_transactions():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    response = table.scan(Select='COUNT')
    return response.get('Count', 0)

def get_total_revenue():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    # Solo sumar transacciones de tipo 'purchase' o 'coin_purchase_mp'
    response = table.scan(
        FilterExpression='transaction_type IN (:purchase, :coin_purchase)',
        ExpressionAttributeValues={
            ':purchase': 'purchase',
            ':coin_purchase': 'coin_purchase_mp'
        }
    )
    total = 0
    for item in response.get('Items', []):
        total += int(item.get('coins_amount', 0))
    return total

def get_average_order_value():
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    response = table.scan(
        FilterExpression='transaction_type IN (:purchase, :coin_purchase)',
        ExpressionAttributeValues={
            ':purchase': 'purchase',
            ':coin_purchase': 'coin_purchase_mp'
        }
    )
    total = 0
    count = 0
    for item in response.get('Items', []):
        total += int(item.get('coins_amount', 0))
        count += 1
    return (total / count) if count > 0 else 0

def get_recent_admin_requests(limit=5):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(ADMIN_REQUEST_TABLE)
    response = table.scan(
        FilterExpression='#status = :pending',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':pending': 'pending'}
    )
    # Ordenar por fecha descendente y limitar
    items = sorted(response.get('Items', []), key=lambda x: x.get('created_at', 0), reverse=True)
    return items[:limit] 