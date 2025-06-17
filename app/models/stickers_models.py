import boto3
from boto3.dynamodb.conditions import Key, Attr
import uuid
import time
import json
from datetime import datetime
from config import (
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    DYNAMODB_STICKERS_TABLE
)

# Define table variable from config
STICKERS_TABLE = DYNAMODB_STICKERS_TABLE

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

# Sticker CRUD Functions
def create_sticker(title=None, description=None, image_url=None, tags=None, created_by=None, 
                  is_public=True, metadata=None, category="user_generated", style=None, 
                  format="PNG", generation_cost=0, prompt=None):
    """
    Create a new sticker record.
    
    Args:
        title (str, optional): Title or name of the sticker
        description (str, optional): Description of the sticker
        image_url (str): URL of the sticker image
        tags (list, optional): List of tags for search
        created_by (str, optional): User ID who created the sticker
        is_public (bool): Whether the sticker is visible to other users
        metadata (dict, optional): Extra fields for AI (model used, configuration, etc.)
        category (str): Category of sticker ("user_generated", "library", "template", etc.)
        style (str, optional): Style used for generation
        format (str): Image format (PNG, SVG, etc.)
        generation_cost (int): Cost in coins to generate this sticker
        prompt (str, optional): Original prompt used to generate the sticker
        
    Returns:
        dict: Created sticker data
    """
    if not image_url:
        raise ValueError("image_url is required")
    
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    sticker_id = str(uuid.uuid4())
    timestamp = int(time.time())
    
    sticker_data = {
        'id': sticker_id,
        'image_url': image_url,
        'created_at': timestamp,
        'updated_at': timestamp,
        'is_public': is_public,
        'is_active': True,
        'category': category,
        'format': format,
        'generation_cost': generation_cost,
        'usage_count': 0
    }
    
    # Add optional fields if provided
    if title:
        sticker_data['title'] = title
    if description:
        sticker_data['description'] = description
    if tags and isinstance(tags, list):
        sticker_data['tags'] = set(tags)  # DynamoDB StringSet
    if created_by:
        sticker_data['created_by'] = created_by
    if metadata:
        sticker_data['metadata'] = metadata
    if style:
        sticker_data['style'] = style
    if prompt:
        sticker_data['prompt'] = prompt
    
    table.put_item(Item=sticker_data)
    return sticker_data

def get_sticker(sticker_id):
    """
    Get sticker by ID.
    
    Args:
        sticker_id (str): Sticker ID to lookup
        
    Returns:
        dict or None: Sticker data if found, None otherwise
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        response = table.get_item(
            Key={'id': sticker_id}
        )
        
        sticker = response.get('Item')
        if sticker and sticker.get('is_active', True):
            return sticker
        return None
    except Exception as e:
        print(f"Error getting sticker {sticker_id}: {e}")
        return None

def get_stickers_by_user(user_id, limit=50, include_inactive=False):
    """
    Get stickers created by a specific user.
    
    Args:
        user_id (str): User ID to get stickers for
        limit (int): Maximum number of stickers to return
        include_inactive (bool): Whether to include inactive stickers
        
    Returns:
        list: List of sticker dictionaries
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        # Build filter expression
        filter_expression = Key('created_by').eq(user_id)
        if not include_inactive:
            filter_expression = filter_expression & Attr('is_active').eq(True)
        
        response = table.query(
            IndexName='CreatedByIndex',
            KeyConditionExpression=Key('created_by').eq(user_id),
            FilterExpression=None if include_inactive else Attr('is_active').eq(True),
            ScanIndexForward=False,  # Sort descending (newest first)
            Limit=limit
        )
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error getting stickers for user {user_id}: {e}")
        return []

def get_public_stickers(limit=50, category=None, style=None):
    """
    Get public and active stickers.
    
    Args:
        limit (int): Maximum number of stickers to return
        category (str, optional): Filter by category
        style (str, optional): Filter by style
        
    Returns:
        list: List of public sticker dictionaries
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        # Build filter expression
        filter_expression = Attr('is_public').eq(True) & Attr('is_active').eq(True)
        
        if style:
            filter_expression = filter_expression & Attr('style').eq(style)
        
        if category:
            # Use CategoryIndex for more efficient querying
            response = table.query(
                IndexName='CategoryIndex',
                KeyConditionExpression=Key('category').eq(category),
                FilterExpression=filter_expression,
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=limit
            )
        else:
            # Use scan when no category specified
            response = table.scan(
                FilterExpression=filter_expression,
                Limit=limit
            )
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error getting public stickers: {e}")
        # Fallback to scan if query fails
        try:
            response = table.scan(
                FilterExpression=filter_expression,
                Limit=limit
            )
            return response.get('Items', [])
        except Exception as scan_error:
            print(f"Error scanning public stickers: {scan_error}")
            return []

def update_sticker(sticker_id, updates):
    """
    Update sticker fields.
    
    Args:
        sticker_id (str): Sticker ID to update
        updates (dict): Dictionary of fields to update
        
    Returns:
        dict or None: Updated sticker data if successful, None otherwise
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    # Build update expression
    update_expression_parts = []
    expression_attribute_values = {}
    expression_attribute_names = {}
    
    # Always update the updated_at timestamp
    updates['updated_at'] = int(time.time())
    
    for key, value in updates.items():
        if key == 'id':  # Don't allow updating the primary key
            continue
            
        # Handle reserved words
        if key in ['format']:
            attr_name = f"#{key}"
            expression_attribute_names[attr_name] = key
            update_expression_parts.append(f"{attr_name} = :{key}")
        else:
            update_expression_parts.append(f"{key} = :{key}")
        
        expression_attribute_values[f":{key}"] = value
    
    if not update_expression_parts:
        return None
    
    update_expression = "SET " + ", ".join(update_expression_parts)
    
    try:
        response = table.update_item(
            Key={'id': sticker_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names if expression_attribute_names else None,
            ReturnValues='ALL_NEW'
        )
        
        return response.get('Attributes')
    except Exception as e:
        print(f"Error updating sticker {sticker_id}: {e}")
        return None

def delete_sticker(sticker_id, soft_delete=True):
    """
    Delete a sticker (soft delete by default).
    
    Args:
        sticker_id (str): Sticker ID to delete
        soft_delete (bool): Whether to soft delete (set is_active=False) or hard delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    if soft_delete:
        # Soft delete: set is_active to False
        result = update_sticker(sticker_id, {'is_active': False})
        return result is not None
    else:
        # Hard delete: remove from table
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(STICKERS_TABLE)
        
        try:
            table.delete_item(Key={'id': sticker_id})
            return True
        except Exception as e:
            print(f"Error deleting sticker {sticker_id}: {e}")
            return False

def increment_usage_count(sticker_id):
    """
    Increment the usage count of a sticker.
    
    Args:
        sticker_id (str): Sticker ID to increment usage for
        
    Returns:
        dict or None: Updated sticker data if successful, None otherwise
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        response = table.update_item(
            Key={'id': sticker_id},
            UpdateExpression='ADD usage_count :inc SET updated_at = :timestamp',
            ExpressionAttributeValues={
                ':inc': 1,
                ':timestamp': int(time.time())
            },
            ReturnValues='ALL_NEW'
        )
        
        return response.get('Attributes')
    except Exception as e:
        print(f"Error incrementing usage count for sticker {sticker_id}: {e}")
        return None

def search_stickers_by_tags(tags, limit=50, is_public_only=True):
    """
    Search stickers by tags.
    
    Args:
        tags (list): List of tags to search for
        limit (int): Maximum number of stickers to return
        is_public_only (bool): Whether to search only public stickers
        
    Returns:
        list: List of matching sticker dictionaries
    """
    if not tags or not isinstance(tags, list):
        return []
    
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        # Build filter expression for tags
        tag_conditions = []
        for tag in tags:
            tag_conditions.append(Attr('tags').contains(tag))
        
        # Combine all tag conditions with OR
        filter_expression = tag_conditions[0]
        for condition in tag_conditions[1:]:
            filter_expression = filter_expression | condition
        
        # Add public and active filters
        if is_public_only:
            filter_expression = filter_expression & Attr('is_public').eq(True)
        filter_expression = filter_expression & Attr('is_active').eq(True)
        
        response = table.scan(
            FilterExpression=filter_expression,
            Limit=limit
        )
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error searching stickers by tags {tags}: {e}")
        return []

def get_stickers_by_category(category, limit=50, is_public_only=True):
    """
    Get stickers by category.
    
    Args:
        category (str): Category to filter by
        limit (int): Maximum number of stickers to return
        is_public_only (bool): Whether to get only public stickers
        
    Returns:
        list: List of sticker dictionaries
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        # Build filter expression
        filter_expression = Attr('category').eq(category) & Attr('is_active').eq(True)
        if is_public_only:
            filter_expression = filter_expression & Attr('is_public').eq(True)
        
        response = table.query(
            IndexName='CategoryIndex',
            KeyConditionExpression=Key('category').eq(category),
            FilterExpression=filter_expression,
            ScanIndexForward=False,  # Sort descending (newest first)
            Limit=limit
        )
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error getting stickers by category {category}: {e}")
        # Fallback to scan if index query fails
        try:
            response = table.scan(
                FilterExpression=filter_expression,
                Limit=limit
            )
            return response.get('Items', [])
        except Exception as scan_error:
            print(f"Error scanning stickers by category: {scan_error}")
            return []

def get_recent_stickers(limit=20, is_public_only=True, category=None):
    """
    Get the most recently created stickers.
    
    Args:
        limit (int): Maximum number of stickers to return
        is_public_only (bool): Whether to get only public stickers
        category (str, optional): Filter by specific category
        
    Returns:
        list: List of recent sticker dictionaries sorted by creation date
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(STICKERS_TABLE)
    
    try:
        # Build filter expression
        filter_expression = Attr('is_active').eq(True)
        if is_public_only:
            filter_expression = filter_expression & Attr('is_public').eq(True)
        
        if category:
            # Use the CreatedAtIndex with category as partition key
            response = table.query(
                IndexName='CreatedAtIndex',
                KeyConditionExpression=Key('category').eq(category),
                FilterExpression=filter_expression,
                ScanIndexForward=False,  # Sort descending (newest first)
                Limit=limit
            )
        else:
            # Query each common category and combine results
            all_items = []
            categories = ['user_generated', 'library', 'template']
            
            for cat in categories:
                try:
                    response = table.query(
                        IndexName='CreatedAtIndex',
                        KeyConditionExpression=Key('category').eq(cat),
                        FilterExpression=filter_expression,
                        ScanIndexForward=False,
                        Limit=limit // len(categories) + 5  # Get a few more per category
                    )
                    all_items.extend(response.get('Items', []))
                except Exception:
                    continue
            
            # Sort all items by created_at and return the most recent
            all_items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            return all_items[:limit]
        
        return response.get('Items', [])
    except Exception as e:
        print(f"Error getting recent stickers: {e}")
        # Fallback to scan if index query fails
        try:
            response = table.scan(
                FilterExpression=filter_expression,
                Limit=limit * 2  # Get more to sort properly
            )
            # Sort by created_at in Python since we can't use the index
            items = response.get('Items', [])
            return sorted(items, key=lambda x: x.get('created_at', 0), reverse=True)[:limit]
        except Exception as scan_error:
            print(f"Error scanning recent stickers: {scan_error}")
            return []
