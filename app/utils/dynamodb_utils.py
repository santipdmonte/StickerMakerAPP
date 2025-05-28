import boto3
from boto3.dynamodb.conditions import Key, Attr
import uuid
import time
import json
import random
import string
from datetime import datetime
from config import (
    INITIAL_COINS, BONUS_COINS,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    DYNAMODB_USER_TABLE, DYNAMODB_TRANSACTION_TABLE, DYNAMODB_REQUEST_TABLE
)

# Define table variables from config
USER_TABLE = DYNAMODB_USER_TABLE
TRANSACTION_TABLE = DYNAMODB_TRANSACTION_TABLE
ADMIN_REQUEST_TABLE = DYNAMODB_REQUEST_TABLE

# Function to check if table is ready (not in CREATING or UPDATING state)
def is_table_ready(table_name):
    dynamodb = get_dynamodb_client()
    try:
        response = dynamodb.describe_table(TableName=table_name)
        status = response['Table']['TableStatus']
        return status == 'ACTIVE'
    except Exception as e:
        print(f"Error checking table status: {e}")
        return False

# Function to verify EmailIndex exists
def verify_email_index():
    """
    Verify the EmailIndex exists on the user table, try to fix if not.
    Returns True if index exists or was created, False otherwise.
    """
    dynamodb = get_dynamodb_client()
    
    try:
        # Check if the table exists first
        response = dynamodb.describe_table(TableName=USER_TABLE)
        
        # Get table billing mode - Note: There seems to be an issue with billing mode detection
        # To be safe, we'll assume PAY_PER_REQUEST to avoid provisioning errors
        billing_mode = "PAY_PER_REQUEST"  # Force this mode for safety
        print(f"Assuming table {USER_TABLE} billing mode: {billing_mode}")
        
        # Check if the EmailIndex exists
        email_index_exists = False
        for index in response['Table'].get('GlobalSecondaryIndexes', []):
            if index['IndexName'] == 'EmailIndex':
                email_index_exists = True
                # Check if the index is in a good state
                if index['IndexStatus'] != 'ACTIVE':
                    print(f"EmailIndex exists but is in {index['IndexStatus']} state")
                    # Wait for it to be active
                    return False
                break
        
        if not email_index_exists:
            print(f"EmailIndex not found on {USER_TABLE}, trying to add it...")
            
            # Create the index definition without provisioned throughput
            index_create_params = {
                'IndexName': 'EmailIndex',
                'KeySchema': [
                    {'AttributeName': 'email', 'KeyType': 'HASH'},
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            }
            
            # Add the GSI to the existing table
            update_params = {
                'TableName': USER_TABLE,
                'AttributeDefinitions': [
                    {'AttributeName': 'email', 'AttributeType': 'S'},
                ],
                'GlobalSecondaryIndexUpdates': [
                    {
                        'Create': index_create_params
                    }
                ]
            }
            
            # Execute the update
            dynamodb.update_table(**update_params)
            print(f"Added EmailIndex to {USER_TABLE}, index will be active soon")
            return False  # Index is being created, not ready yet
        
        return True  # Index exists and is active
        
    except Exception as e:
        print(f"Error verifying EmailIndex: {e}")
        return False

# Temporary workaround to find a user by email without using the index
def find_user_by_email_scan(email):
    """
    Fallback method to find a user by email using scan instead of query
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    response = table.scan(
        FilterExpression=Attr('email').eq(email)
    )
    
    items = response.get('Items', [])
    return items[0] if items else None

def get_dynamodb_client():
    """
    Returns a boto3 DynamoDB client using environment variables for credentials.
    """
    aws_access_key = AWS_ACCESS_KEY_ID
    aws_secret_key = AWS_SECRET_ACCESS_KEY
    aws_region = AWS_REGION
    
    if not aws_access_key or not aws_secret_key:
        raise ValueError("AWS credentials not found in environment variables")
    
    return boto3.client(
        'dynamodb',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )

def get_dynamodb_resource():
    """
    Returns a boto3 DynamoDB resource using environment variables for credentials.
    """
    aws_access_key = AWS_ACCESS_KEY_ID
    aws_secret_key = AWS_SECRET_ACCESS_KEY
    aws_region = AWS_REGION
    
    if not aws_access_key or not aws_secret_key:
        raise ValueError("AWS credentials not found in environment variables")
    
    return boto3.resource(
        'dynamodb',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )

def ensure_tables_exist():
    """
    Ensures that the DynamoDB tables exist, creates them if they don't.
    """
    dynamodb = get_dynamodb_resource()
    existing_tables = dynamodb.meta.client.list_tables()['TableNames']
    
    # Create user table if it doesn't exist
    if USER_TABLE not in existing_tables:
        dynamodb.create_table(
            TableName=USER_TABLE,
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'EmailIndex',
                    'KeySchema': [
                        {'AttributeName': 'email', 'KeyType': 'HASH'},
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"Created table {USER_TABLE}")
    
    # Create transaction table if it doesn't exist
    if TRANSACTION_TABLE not in existing_tables:
        dynamodb.create_table(
            TableName=TRANSACTION_TABLE,
            KeySchema=[
                {'AttributeName': 'transaction_id', 'KeyType': 'HASH'},  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'transaction_id', 'AttributeType': 'S'},
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'payment_id', 'AttributeType': 'S'},  # Nuevo atributo para payment_id
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'UserIdIndex',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'PaymentIdIndex',  # Nuevo índice para búsquedas por payment_id
                    'KeySchema': [
                        {'AttributeName': 'payment_id', 'KeyType': 'HASH'},
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"Created table {TRANSACTION_TABLE}")
    
    # Si la tabla de transacciones ya existe, verificar si tiene el índice PaymentIdIndex
    # y crearlo si no existe
    elif TRANSACTION_TABLE in existing_tables:
        try:
            # Obtenemos la descripción de la tabla
            table_description = dynamodb.meta.client.describe_table(TableName=TRANSACTION_TABLE)
            
            # Verificamos si el índice ya existe
            payment_id_index_exists = False
            if 'GlobalSecondaryIndexes' in table_description['Table']:
                for index in table_description['Table']['GlobalSecondaryIndexes']:
                    if index['IndexName'] == 'PaymentIdIndex':
                        payment_id_index_exists = True
                        break
            
            # Si el índice no existe, lo creamos
            if not payment_id_index_exists:
                print(f"Adding PaymentIdIndex to {TRANSACTION_TABLE}...")
                
                # Primero verificamos si el atributo payment_id existe en la definición
                payment_id_defined = False
                for attr_def in table_description['Table'].get('AttributeDefinitions', []):
                    if attr_def['AttributeName'] == 'payment_id':
                        payment_id_defined = True
                        break
                
                # Preparamos las definiciones de atributos según sea necesario
                attribute_definitions = []
                if not payment_id_defined:
                    attribute_definitions.append({
                        'AttributeName': 'payment_id',
                        'AttributeType': 'S'
                    })
                
                # Actualizamos la tabla para agregar el índice
                dynamodb.meta.client.update_table(
                    TableName=TRANSACTION_TABLE,
                    AttributeDefinitions=attribute_definitions if attribute_definitions else None,
                    GlobalSecondaryIndexUpdates=[
                        {
                            'Create': {
                                'IndexName': 'PaymentIdIndex',
                                'KeySchema': [
                                    {'AttributeName': 'payment_id', 'KeyType': 'HASH'},
                                ],
                                'Projection': {
                                    'ProjectionType': 'ALL'
                                },
                                'ProvisionedThroughput': {
                                    'ReadCapacityUnits': 5,
                                    'WriteCapacityUnits': 5
                                }
                            }
                        }
                    ]
                )
                print(f"PaymentIdIndex added to {TRANSACTION_TABLE}")
        except Exception as e:
            print(f"Error checking/updating PaymentIdIndex: {e}")

    # Tabla de solicitudes de admin
    if ADMIN_REQUEST_TABLE not in existing_tables:
        dynamodb.create_table(
            TableName=ADMIN_REQUEST_TABLE,
            KeySchema=[
                {'AttributeName': 'token', 'KeyType': 'HASH'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'token', 'AttributeType': 'S'},
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"Created table {ADMIN_REQUEST_TABLE}")

# User Management Functions
def create_user(email, initial_coins=None, name=None, role='user', referral=None):
    """
    Create a new user with the provided email.
    
    Args:
        email (str): User's email address
        initial_coins (int): Initial number of coins to assign (defaults to BONUS_COINS env var)
        name (str): User's name
        role (str): User role (default 'user')
        referral (str): Referral code or source (optional)
        
    Returns:
        dict: User data including user_id
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # Check if user with this email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return existing_user
    
    # Use provided initial_coins or default to BONUS_COINS from env var
    if initial_coins is None:
        initial_coins = BONUS_COINS
    
    # Create new user
    user_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    user_data = {
        'user_id': user_id,
        'email': email,
        'coins': initial_coins,
        'created_at': timestamp,
        'updated_at': timestamp,
        'last_login': timestamp,
        'role': role,
        'status': 'active',
        'referral': referral
    }
    
    # Add optional fields if provided
    if name:
        user_data['name'] = name
    if referral:
        user_data['referral'] = referral
    
    table.put_item(Item=user_data)
    return user_data

def get_user(user_id):
    """
    Get user by user_id
    
    Args:
        user_id (str): User ID to lookup
        
    Returns:
        dict or None: User data if found, None otherwise
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    try:
        response = table.get_item(
            Key={'user_id': user_id}
        )
        
        return response.get('Item')
    except Exception:
        return None

def get_user_by_email(email):
    """
    Get user by email
    
    Args:
        email (str): Email to lookup
        
    Returns:
        dict or None: User data if found, None otherwise
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # First try to verify that the index exists
    if not verify_email_index():
        # If index doesn't exist or is being created, use scan as fallback
        print(f"Using scan fallback to find user with email {email}")
        return find_user_by_email_scan(email)
    
    try:
        # Query the email GSI
        response = table.query(
            IndexName='EmailIndex',
            KeyConditionExpression=Key('email').eq(email)
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        print(f"Error querying EmailIndex: {e}, falling back to scan")
        return find_user_by_email_scan(email)


def update_user_last_login(user_id):
    """
    Update a user's last login timestamp
    
    Args:
        user_id (str): User ID to update
        
    Returns:
        dict: Updated user data
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    timestamp = int(time.time())
    
    response = table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET last_login = :timestamp',
        ExpressionAttributeValues={
            ':timestamp': timestamp
        },
        ReturnValues='ALL_NEW'
    )
    
    return response.get('Attributes')

# Pin generation and verification
def generate_pin(length=6):
    """
    Generate a random PIN of specified length.
    
    Args:
        length (int): Length of the PIN
        
    Returns:
        str: Generated PIN
    """
    return ''.join(random.choices(string.digits, k=length))

def store_login_pin(email, pin, expiry_seconds=600, create_if_not_exists=False):
    """
    Store a login PIN for a user
    
    Args:
        email (str): User's email
        pin (str): The PIN to store
        expiry_seconds (int): How long the PIN is valid for in seconds
        create_if_not_exists (bool): Whether to create a user if one doesn't exist
        
    Returns:
        tuple: (bool success, bool user_exists)
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # Get user by email
    user = get_user_by_email(email)
    is_new_user = False
    
    if not user:
        if not create_if_not_exists:
            # Return success=True but user_exists=False
            return True, False
            
        # Create user if doesn't exist with default bonus coins value
        user = create_user(email, BONUS_COINS)
        is_new_user = True
    
    user_id = user['user_id']
    expiry_time = int(time.time()) + expiry_seconds
    
    # Update user with PIN and new user flag if applicable
    update_expression = 'SET login_pin = :pin, pin_expiry = :expiry'
    expression_values = {
        ':pin': pin,
        ':expiry': expiry_time
    }
    
    if is_new_user:
        update_expression += ', is_new_user = :is_new'
        expression_values[':is_new'] = True
    
    # Update user with PIN
    response = table.update_item(
        Key={'user_id': user_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
        ReturnValues='UPDATED_NEW'
    )
    
    return bool(response.get('Attributes')), True

def verify_login_pin(email, pin):
    """
    Verify a login PIN for a user
    
    Args:
        email (str): User's email
        pin (str): The PIN to verify
        
    Returns:
        dict or None: User data if PIN is valid, None otherwise
    """
    user = get_user_by_email(email)
    if not user:
        return None
    
    stored_pin = user.get('login_pin')
    pin_expiry = user.get('pin_expiry', 0)
    current_time = int(time.time())
    is_new_user = user.get('is_new_user', False)
    
    if stored_pin == pin and current_time < pin_expiry:
        # Update last login time
        updated_user = update_user_last_login(user['user_id'])
        
        # Remove the PIN after successful verification, but keep is_new_user if it exists
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(USER_TABLE)
        
        # Choose update expression based on whether this is a new user
        if is_new_user:
            table.update_item(
                Key={'user_id': user['user_id']},
                UpdateExpression='REMOVE login_pin, pin_expiry'
            )
            
            # Ensure is_new_user is set in the updated user
            if updated_user and 'is_new_user' not in updated_user:
                updated_user['is_new_user'] = True
        else:
            table.update_item(
                Key={'user_id': user['user_id']},
                UpdateExpression='REMOVE login_pin, pin_expiry, is_new_user'
            )
        
        return updated_user
    
    return None

# Transaction Management Functions
def create_transaction(user_id, coins_amount, transaction_type, details=None, payment_id=None):
    """
    Record a transaction in the transaction table and update user's coin balance
    
    Args:
        user_id (str): The user ID associated with this transaction
        coins_amount (int): Number of coins (positive for additions, negative for subtractions)
        transaction_type (str): Type of transaction (e.g., 'purchase', 'usage', 'bonus', 'coin_purchase_mp')
        details (dict): Any additional details about the transaction
        payment_id (str, optional): ID de pago externo para transacciones de compra, usado para idempotencia
        
    Returns:
        dict: Transaction data with additional 'is_existing' field if transaction already existed
    """
    dynamodb = get_dynamodb_resource()
    transaction_table = dynamodb.Table(TRANSACTION_TABLE)
    user_table = dynamodb.Table(USER_TABLE)
    
    # Si se proporciona payment_id, verificar si ya existe una transacción con ese payment_id
    if payment_id:
        existing_transaction = get_transaction_by_payment_id(payment_id)
        if existing_transaction:
            print(f"Transaction with payment_id {payment_id} already exists, returning existing transaction")
            # Marcar la transacción como existente para poder distinguirla
            existing_transaction['is_existing'] = True
            return existing_transaction

    transaction_id = str(uuid.uuid4())
    timestamp = int(time.time())
    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

    valid_transaction_types = ['purchase', 'usage', 'bonus', 'coin_purchase_mp', 'sticker_generation_authenticated']
    if transaction_type not in valid_transaction_types:
        raise ValueError(f"Invalid transaction type: {transaction_type}, must be one of: {', '.join(valid_transaction_types)}")
    
    transaction_data = {
        'transaction_id': transaction_id,
        'user_id': user_id,
        'coins_amount': coins_amount,
        'transaction_type': transaction_type,
        'timestamp': timestamp,
        'date': date_str,
        'details': details or {}
    }
    
    # Añadir payment_id si está definido
    if payment_id:
        transaction_data['payment_id'] = str(payment_id)
    
    # Record the transaction
    transaction_table.put_item(Item=transaction_data)
    
    # Update user's coin balance
    # First get current user data
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found")
    
    # Update coins and timestamp
    current_coins = user.get('coins', 0)
    new_coins = max(0, current_coins + coins_amount)  # Prevent negative coins
    
    # Update the user's coin balance
    response = user_table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET coins = :coins, updated_at = :timestamp',
        ExpressionAttributeValues={
            ':coins': new_coins,
            ':timestamp': timestamp
        },
        ReturnValues='ALL_NEW'
    )
    
    # Return the transaction data and the updated user data
    transaction_data['updated_user'] = response.get('Attributes')
    # Marcar explícitamente como transacción nueva
    transaction_data['is_existing'] = False
    return transaction_data

def get_user_transactions(user_id, limit=50):
    """
    Get recent transactions for a user
    
    Args:
        user_id (str): User ID to get transactions for
        limit (int): Maximum number of transactions to return
        
    Returns:
        list: List of transaction dictionaries
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    
    response = table.query(
        IndexName='UserIdIndex',
        KeyConditionExpression=Key('user_id').eq(user_id),
        ScanIndexForward=False,  # Sort descending (newest first)
        Limit=limit
    )
    
    return response.get('Items', [])

def get_transaction_by_payment_id(payment_id):
    """
    Busca una transacción por su payment_id de Mercado Pago
    
    Args:
        payment_id (str): ID de pago de Mercado Pago
        
    Returns:
        dict or None: Datos de la transacción o None si no se encuentra
    """
    if not payment_id:
        return None
        
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    
    try:
        # Usar el índice PaymentIdIndex para buscar eficientemente
        response = table.query(
            IndexName='PaymentIdIndex',
            KeyConditionExpression=Key('payment_id').eq(str(payment_id)),
            Limit=1  # Solo necesitamos una transacción
        )
        
        items = response.get('Items', [])
        if items:
            return items[0]
        return None
    except Exception as e:
        print(f"Error querying transaction by payment_id: {e}")
        return None

# Admin Functions
def create_admin_request(user_id, email):
    token = str(uuid.uuid4())
    timestamp = int(time.time())
    item = {
        'token': token,
        'user_id': user_id,
        'email': email,
        'created_at': timestamp,
        'status': 'pending'
    }
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(ADMIN_REQUEST_TABLE)
    table.put_item(Item=item)
    return token

def get_admin_request(token):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(ADMIN_REQUEST_TABLE)
    response = table.get_item(Key={'token': token})
    return response.get('Item')

def approve_admin_request(token):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(ADMIN_REQUEST_TABLE)
    table.update_item(
        Key={'token': token},
        UpdateExpression='SET #s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': 'approved'}
    )

def update_user_role(user_id, new_role):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    response = table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET #r = :role',
        ExpressionAttributeNames={'#r': 'role'},
        ExpressionAttributeValues={':role': new_role},
        ReturnValues='ALL_NEW'
    )
    return response.get('Attributes') 