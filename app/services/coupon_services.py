# Servicios para la gestión de cupones
from utils.dynamodb_utils import get_dynamodb_resource, COUPON_TABLE, TRANSACTION_TABLE, get_user
import uuid
import time
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from utils.utils import safe_int, safe_decimal
from utils.dynamodb_utils import create_transaction

# Crear cupón
def create_coupon(data):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(COUPON_TABLE)
    now = int(time.time())
    # Validar unicidad del código de cupón
    existing = get_coupon_by_code(data['coupon_code'])
    if existing:
        raise Exception('Ya existe un cupón con ese código.')
    item = {
        'id_coupon': str(uuid.uuid4()),
        'coupon_code': data['coupon_code'],
        'coupons_left': safe_int(data.get('coupons_left', 1), 1),
        'coupon_initial_number': safe_int(data.get('coupon_initial_number', data.get('coupons_left', 1)), 1),
        'is_active': safe_int(data.get('is_active', 1), 1),
        'expires_at': safe_int(data.get('expires_at', 0), 0),
        'coupon_type': data.get('coupon_type', 'coins'),
        'coins_value': safe_decimal(data.get('coins_value', 0), 0),
        'discount_percent': safe_decimal(data.get('discount_percent', 0), 0),
        'created_at': now,
        'modified_at': now
    }
    table.put_item(Item=item)
    return item

# Obtener cupón por código
def get_coupon_by_code(coupon_code):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(COUPON_TABLE)
    resp = table.query(
        IndexName='CouponCodeIndex',
        KeyConditionExpression=Key('coupon_code').eq(coupon_code)
    )
    items = resp.get('Items', [])
    return items[0] if items else None

# Listar cupones (con filtros opcionales)
def list_coupons(filters=None):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(COUPON_TABLE)
    scan_kwargs = {}
    if filters:
        filter_expr = None
        for k, v in filters.items():
            cond = Attr(k).eq(v)
            filter_expr = cond if filter_expr is None else filter_expr & cond
        if filter_expr is not None:
            scan_kwargs['FilterExpression'] = filter_expr
    resp = table.scan(**scan_kwargs)
    return resp.get('Items', [])

# Redimir cupón
def redeem_coupon(user_id, coupon_code):
    dynamodb = get_dynamodb_resource()
    coupon_table = dynamodb.Table(COUPON_TABLE)
    transaction_table = dynamodb.Table(TRANSACTION_TABLE)
    # 1. Buscar cupón
    coupon = get_coupon_by_code(coupon_code)
    if not coupon:
        return {'error': 'Cupón no encontrado'}, 404
    if not coupon.get('is_active', 1):
        return {'error': 'Cupón inactivo'}, 400
    if coupon.get('expires_at', 0) and int(time.time()) > int(coupon['expires_at']):
        return {'error': 'Cupón expirado'}, 400

    # 2. Verificar si el usuario ya usó el cupón
    resp = transaction_table.query(
        IndexName='CouponCodeIndex',
        KeyConditionExpression=Key('coupon_code').eq(coupon_code),
        FilterExpression=Attr('user_id').eq(user_id)
    )
    if resp.get('Items'):
        return {'error': 'Ya has usado este cupón'}, 400
    # 3. Aplicar beneficio (solo lógica de monedas por ahora)
    coins_value = Decimal(str(coupon.get('coins_value', 0)))
    discount_percent = Decimal(str(coupon.get('discount_percent', 0)))
    if coins_value <= 0 and discount_percent <= 0:
        return {'error': 'Cupón sin beneficio'}, 400
    # 4. Registrar transacción
    transaction = create_transaction(
        user_id=user_id,
        coins_amount=coins_value,
        transaction_type='coupon',
        details={
            'id_coupon': coupon['id_coupon'],
            'discount_percent': Decimal(str(discount_percent))
        },
        coupon_code=coupon_code
    )
    # 5. Restar usos al cupón
    coupon_table.update_item(
        Key={'id_coupon': coupon['id_coupon']},
        UpdateExpression='SET coupons_left = coupons_left - :dec, modified_at = :now',
        ExpressionAttributeValues={':dec': 1, ':now': int(time.time())}
    )
    # 6. Si los usos llegan a 0, desactivar el cupón
    updated_coupon = get_coupon_by_code(coupon_code)
    if int(updated_coupon.get('coupons_left', 0)) <= 0 and int(updated_coupon.get('is_active', 1)) == 1:
        coupon_table.update_item(
            Key={'id_coupon': coupon['id_coupon']},
            UpdateExpression='SET is_active = :inactive, modified_at = :now',
            ExpressionAttributeValues={':inactive': 0, ':now': int(time.time())}
        )
    return {'success': True, 'coins_added': float(coins_value), 'discount_percent': float(discount_percent)}

# Activar/desactivar cupón
def set_coupon_active(coupon_code, is_active):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(COUPON_TABLE)
    coupon = get_coupon_by_code(coupon_code)
    if not coupon:
        return {'error': 'Cupón no encontrado'}, 404
    table.update_item(
        Key={'id_coupon': coupon['id_coupon']},
        UpdateExpression='SET is_active = :active, modified_at = :now',
        ExpressionAttributeValues={':active': int(is_active), ':now': int(time.time())}
    )
    return {'success': True}

# Eliminar cupón
def delete_coupon(coupon_code):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(COUPON_TABLE)
    coupon = get_coupon_by_code(coupon_code)
    if not coupon:
        return {'error': 'Cupón no encontrado'}, 404
    table.delete_item(Key={'id_coupon': coupon['id_coupon']})
    return {'success': True}

def get_coupon_redemptions(coupon_code):
    """
    Devuelve una lista de usuarios que usaron el cupón, con nombre, email y fecha de redención.
    """
    dynamodb = get_dynamodb_resource()
    transaction_table = dynamodb.Table(TRANSACTION_TABLE)
    # Buscar todas las transacciones con ese coupon_code
    resp = transaction_table.query(
        IndexName='CouponCodeIndex',
        KeyConditionExpression=Key('coupon_code').eq(coupon_code)
    )
    items = resp.get('Items', [])
    redemptions = []
    for tx in items:
        user_id = tx.get('user_id')
        timestamp = tx.get('timestamp')
        fecha = datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S') if timestamp else None
        user = get_user(user_id) if user_id else None
        nombre = user.get('name') if user else None
        email = user.get('email') if user else None
        redemptions.append({
            'user_id': user_id,
            'nombre': nombre,
            'email': email,
            'fecha': fecha
        })
    return redemptions
