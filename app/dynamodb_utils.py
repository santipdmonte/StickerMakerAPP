import os
import boto3
from boto3.dynamodb.conditions import Key, Attr
import uuid
import time
import json
import random
import string
from datetime import datetime

# DynamoDB table names from environment variables
USER_TABLE = os.getenv('DYNAMODB_USER_TABLE', 'test-thestickerhouse-users')
TRANSACTION_TABLE = os.getenv('DYNAMODB_TRANSACTION_TABLE', 'test-thestickerhouse-transactions')

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
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
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
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
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
    
    # Check if tables exist
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
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"Created table {TRANSACTION_TABLE}")

# User Management Functions
def create_user(email, initial_coins=85):
    """
    Create a new user with the provided email.
    
    Args:
        email (str): User's email address
        initial_coins (int): Initial number of coins to assign
        
    Returns:
        dict: User data including user_id
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # Check if user with this email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return existing_user
    
    # Create new user
    user_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    user_data = {
        'user_id': user_id,
        'email': email,
        'coins': initial_coins,
        'created_at': timestamp,
        'updated_at': timestamp,
        'last_login': timestamp
    }
    
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
    
    response = table.get_item(
        Key={'user_id': user_id}
    )
    
    return response.get('Item')

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

def update_user_coins(user_id, coins_change):
    """
    Update a user's coin balance
    
    Args:
        user_id (str): User ID to update
        coins_change (int): Number of coins to add (positive) or subtract (negative)
        
    Returns:
        dict: Updated user data
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # Get current user data
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found")
    
    # Update coins and timestamp
    current_coins = user.get('coins', 0)
    new_coins = max(0, current_coins + coins_change)  # Prevent negative coins
    timestamp = int(time.time())
    
    response = table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET coins = :coins, updated_at = :timestamp',
        ExpressionAttributeValues={
            ':coins': new_coins,
            ':timestamp': timestamp
        },
        ReturnValues='ALL_NEW'
    )
    
    return response.get('Attributes')

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

def store_login_pin(email, pin, expiry_seconds=600):
    """
    Store a login PIN for a user
    
    Args:
        email (str): User's email
        pin (str): The PIN to store
        expiry_seconds (int): How long the PIN is valid for in seconds
        
    Returns:
        bool: True if successful
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(USER_TABLE)
    
    # Get user by email
    user = get_user_by_email(email)
    if not user:
        # Create user if doesn't exist
        user = create_user(email)
    
    user_id = user['user_id']
    expiry_time = int(time.time()) + expiry_seconds
    
    # Update user with PIN
    response = table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='SET login_pin = :pin, pin_expiry = :expiry',
        ExpressionAttributeValues={
            ':pin': pin,
            ':expiry': expiry_time
        },
        ReturnValues='UPDATED_NEW'
    )
    
    return bool(response.get('Attributes'))

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
    
    if stored_pin == pin and current_time < pin_expiry:
        # Update last login time
        updated_user = update_user_last_login(user['user_id'])
        
        # Remove the PIN after successful verification
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(USER_TABLE)
        table.update_item(
            Key={'user_id': user['user_id']},
            UpdateExpression='REMOVE login_pin, pin_expiry'
        )
        
        return updated_user
    
    return None

# Transaction Management Functions
def create_transaction(user_id, coins_amount, transaction_type, details=None):
    """
    Record a transaction in the transaction table
    
    Args:
        user_id (str): The user ID associated with this transaction
        coins_amount (int): Number of coins (positive for additions, negative for subtractions)
        transaction_type (str): Type of transaction (e.g., 'purchase', 'usage', 'bonus')
        details (dict): Any additional details about the transaction
        
    Returns:
        dict: Transaction data
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(TRANSACTION_TABLE)
    
    transaction_id = str(uuid.uuid4())
    timestamp = int(time.time())
    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    
    transaction_data = {
        'transaction_id': transaction_id,
        'user_id': user_id,
        'coins_amount': coins_amount,
        'transaction_type': transaction_type,
        'timestamp': timestamp,
        'date': date_str,
        'details': details or {}
    }
    
    table.put_item(Item=transaction_data)
    
    # Update user's coin balance
    update_user_coins(user_id, coins_amount)
    
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