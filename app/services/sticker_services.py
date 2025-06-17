"""
Sticker Services - Business logic for sticker management
"""
import os
import re
import time
import logging
from typing import List, Dict, Optional, Tuple
from models.stickers_models import (
    create_sticker, get_sticker, get_stickers_by_user, get_public_stickers,
    update_sticker, delete_sticker, increment_usage_count, search_stickers_by_tags,
    get_stickers_by_category, get_recent_stickers
)
from utils.dynamodb_utils import get_user
from config import STICKER_STYLE_CONFIG

# Set up logging
logger = logging.getLogger(__name__)
from flask import session

class StickerValidationError(Exception):
    """Custom exception for sticker validation errors"""
    pass

def validate_sticker_data(image_url: str, title: str = None, description: str = None, 
                         tags: List[str] = None, style: str = None) -> Dict:
    """
    Validate sticker data before creation or update.
    
    Args:
        image_url (str): URL of the sticker image
        title (str, optional): Title of the sticker
        description (str, optional): Description of the sticker
        tags (list, optional): List of tags
        style (str, optional): Style used for generation
        
    Returns:
        dict: Validated data
        
    Raises:
        StickerValidationError: If validation fails
    """
    validated_data = {}
    
    # Validate image_url
    if not image_url or not isinstance(image_url, str):
        raise StickerValidationError("image_url is required and must be a string")
    
    # Basic URL validation
    # url_pattern = r'^https?://.+'
    # if not re.match(url_pattern, image_url):
    #     raise StickerValidationError("image_url must be a valid URL starting with http:// or https://")
    
    validated_data['image_url'] = image_url.strip()
    
    # Validate title
    if title is not None:
        if not isinstance(title, str):
            raise StickerValidationError("title must be a string")
        title = title.strip()
        if len(title) > 100:
            raise StickerValidationError("title must be 100 characters or less")
        if title:
            validated_data['title'] = title
    
    # Validate description
    if description is not None:
        if not isinstance(description, str):
            raise StickerValidationError("description must be a string")
        description = description.strip()
        if len(description) > 500:
            raise StickerValidationError("description must be 500 characters or less")
        if description:
            validated_data['description'] = description
    
    # Validate tags
    if tags is not None:
        if not isinstance(tags, list):
            raise StickerValidationError("tags must be a list")
        
        validated_tags = []
        for tag in tags:
            if not isinstance(tag, str):
                raise StickerValidationError("all tags must be strings")
            tag = tag.strip().lower()
            if tag and len(tag) <= 50:  # Only add non-empty tags under 50 chars
                validated_tags.append(tag)
        
        if len(validated_tags) > 10:
            raise StickerValidationError("maximum 10 tags allowed")
        
        if validated_tags:
            validated_data['tags'] = validated_tags
    
    # Validate style
    if style is not None:
        if not isinstance(style, str):
            raise StickerValidationError("style must be a string")
        if style not in STICKER_STYLE_CONFIG:
            raise StickerValidationError(f"invalid style '{style}'. Valid styles: {list(STICKER_STYLE_CONFIG.keys())}")
        validated_data['style'] = style
    
    return validated_data

def create_user_sticker(user_id: str, image_url: str, image_url_high: str = None, title: str = None, 
                       description: str = None, tags: List[str] = None, 
                       is_public: bool = True, style: str = None, 
                       generation_cost: int = 0, prompt: str = None,
                       metadata: Dict = None) -> Dict:
    """
    Create a new user-generated sticker with validation.
    
    Args:
        user_id (str): ID of the user creating the sticker
        image_url (str): URL of the sticker image (low resolution)
        image_url_high (str, optional): URL of the high resolution sticker image
        title (str, optional): Title of the sticker
        description (str, optional): Description of the sticker
        tags (list, optional): List of tags for search
        is_public (bool): Whether the sticker should be public
        style (str, optional): Style used for generation
        generation_cost (int): Cost in coins to generate this sticker
        prompt (str, optional): Original prompt used to generate the sticker
        metadata (dict, optional): Additional metadata
        
    Returns:
        dict: Created sticker data
        
    Raises:
        StickerValidationError: If validation fails
        ValueError: If user doesn't exist
    """
    
    # Validate sticker data
    validated_data = validate_sticker_data(image_url, title, description, tags, style)
    
    # Validate prompt if provided
    if prompt is not None:
        if not isinstance(prompt, str):
            raise StickerValidationError("prompt must be a string")
        prompt = prompt.strip()
        if len(prompt) > 500:
            raise StickerValidationError("prompt must be 500 characters or less")
    
    # Create sticker
    sticker_data = create_sticker(
        title=validated_data.get('title'),
        description=validated_data.get('description'),
        image_url=validated_data['image_url'],
        image_url_high=image_url_high,
        tags=validated_data.get('tags'),
        created_by=user_id,
        is_public=is_public,
        metadata=metadata,
        category="user_generated",
        style=validated_data.get('style'),
        format="PNG",  # Default format
        generation_cost=generation_cost,
        prompt=prompt
    )
    
    return sticker_data

def create_library_sticker(image_url: str, title: str, image_url_high: str = None, description: str = None,
                          tags: List[str] = None, style: str = None,
                          metadata: Dict = None) -> Dict:
    """
    Create a sticker for the official library.
    
    Args:
        image_url (str): URL of the sticker image (low resolution)
        title (str): Title of the sticker (required for library stickers)
        image_url_high (str, optional): URL of the high resolution sticker image
        description (str, optional): Description of the sticker
        tags (list, optional): List of tags for search
        style (str, optional): Style of the sticker
        metadata (dict, optional): Additional metadata
        
    Returns:
        dict: Created sticker data
        
    Raises:
        StickerValidationError: If validation fails
    """
    if not title:
        raise StickerValidationError("title is required for library stickers")
    
    # Validate sticker data
    validated_data = validate_sticker_data(image_url, title, description, tags, style)
    
    # Create library sticker
    sticker_data = create_sticker(
        title=validated_data['title'],
        description=validated_data.get('description'),
        image_url=validated_data['image_url'],
        image_url_high=image_url_high,
        tags=validated_data.get('tags'),
        created_by=None,  # No specific user for library stickers
        is_public=True,   # Library stickers are always public
        metadata=metadata,
        category="library",
        style=validated_data.get('style'),
        format="PNG",
        generation_cost=0  # Library stickers have no generation cost
    )
    
    return sticker_data

def get_sticker_gallery(category: str = None, style: str = None, tags: List[str] = None,
                       user_id: str = None, limit: int = 50) -> List[Dict]:
    """
    Get stickers for display in gallery with various filters.
    
    Args:
        category (str, optional): Filter by category
        style (str, optional): Filter by style
        tags (list, optional): Filter by tags
        user_id (str, optional): Filter by user (for user's own stickers)
        limit (int): Maximum number of stickers to return
        
    Returns:
        list: List of sticker dictionaries
    """
    if user_id:
        # Get user's own stickers
        return get_stickers_by_user(user_id, limit, include_inactive=False)
    elif tags:
        # Search by tags
        return search_stickers_by_tags(tags, limit, is_public_only=True)
    elif category:
        # Get by category
        return get_stickers_by_category(category, limit, is_public_only=True)
    else:
        # Get public stickers with optional style filter
        return get_public_stickers(limit, category, style)

def use_sticker(sticker_id: str, user_id: str = None) -> Tuple[bool, Dict]:
    """
    Mark a sticker as used and increment its usage count.
    
    Args:
        sticker_id (str): ID of the sticker being used
        user_id (str, optional): ID of the user using the sticker
        
    Returns:
        tuple: (success: bool, sticker_data: dict or None)
    """
    # Get sticker to verify it exists and is active
    sticker = get_sticker(sticker_id)
    if not sticker:
        return False, None
    
    # Increment usage count
    updated_sticker = increment_usage_count(sticker_id)
    
    if updated_sticker:
        return True, updated_sticker
    else:
        return False, sticker

def update_sticker_details(sticker_id: str, user_id: str, updates: Dict) -> Dict:
    """
    Update sticker details with validation and permission checking.
    
    Args:
        sticker_id (str): ID of the sticker to update
        user_id (str): ID of the user making the update
        updates (dict): Dictionary of fields to update
        
    Returns:
        dict: Updated sticker data
        
    Raises:
        ValueError: If sticker not found or user doesn't have permission
        StickerValidationError: If validation fails
    """
    # Get existing sticker
    sticker = get_sticker(sticker_id)
    if not sticker:
        raise ValueError("Sticker not found")
    
    # Check permission (only the creator or admin can update)
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    
    is_admin = user.get('role') == 'admin'
    is_creator = sticker.get('created_by') == user_id
    
    if not (is_admin or is_creator):
        raise ValueError("You don't have permission to update this sticker")
    
    # Validate updates
    validated_updates = {}
    
    if 'title' in updates:
        validated_data = validate_sticker_data(
            sticker['image_url'],  # Use existing image_url for validation
            title=updates['title']
        )
        if 'title' in validated_data:
            validated_updates['title'] = validated_data['title']
    
    if 'description' in updates:
        validated_data = validate_sticker_data(
            sticker['image_url'],
            description=updates['description']
        )
        if 'description' in validated_data:
            validated_updates['description'] = validated_data['description']
    
    if 'tags' in updates:
        validated_data = validate_sticker_data(
            sticker['image_url'],
            tags=updates['tags']
        )
        if 'tags' in validated_data:
            validated_updates['tags'] = validated_data['tags']
    
    if 'is_public' in updates:
        if isinstance(updates['is_public'], bool):
            validated_updates['is_public'] = updates['is_public']
    
    if 'style' in updates:
        validated_data = validate_sticker_data(
            sticker['image_url'],
            style=updates['style']
        )
        if 'style' in validated_data:
            validated_updates['style'] = validated_data['style']
    
    # Update sticker
    if validated_updates:
        updated_sticker = update_sticker(sticker_id, validated_updates)
        if updated_sticker:
            return updated_sticker
        else:
            raise ValueError("Failed to update sticker")
    else:
        return sticker

def delete_user_sticker(sticker_id: str, user_id: str, hard_delete: bool = False) -> bool:
    """
    Delete a sticker with permission checking.
    
    Args:
        sticker_id (str): ID of the sticker to delete
        user_id (str): ID of the user requesting deletion
        hard_delete (bool): Whether to hard delete or soft delete
        
    Returns:
        bool: True if deletion was successful
        
    Raises:
        ValueError: If sticker not found or user doesn't have permission
    """
    # Get existing sticker
    sticker = get_sticker(sticker_id)
    if not sticker:
        raise ValueError("Sticker not found")
    
    # Check permission (only the creator or admin can delete)
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    
    is_admin = user.get('role') == 'admin'
    is_creator = sticker.get('created_by') == user_id
    
    if not (is_admin or is_creator):
        raise ValueError("You don't have permission to delete this sticker")
    
    # Delete sticker
    return delete_sticker(sticker_id, soft_delete=not hard_delete)

def get_user_sticker_stats(user_id: str) -> Dict:
    """
    Get statistics about a user's stickers.
    
    Args:
        user_id (str): User ID to get stats for
        
    Returns:
        dict: Statistics including total stickers, public stickers, total usage, etc.
    """
    # Get all user stickers (including inactive)
    all_stickers = get_stickers_by_user(user_id, limit=1000, include_inactive=True)
    
    stats = {
        'total_stickers': len(all_stickers),
        'active_stickers': 0,
        'public_stickers': 0,
        'private_stickers': 0,
        'total_usage_count': 0,
        'total_generation_cost': 0,
        'categories': {},
        'styles': {}
    }
    
    for sticker in all_stickers:
        if sticker.get('is_active', True):
            stats['active_stickers'] += 1
            
            if sticker.get('is_public', True):
                stats['public_stickers'] += 1
            else:
                stats['private_stickers'] += 1
            
            stats['total_usage_count'] += sticker.get('usage_count', 0)
            stats['total_generation_cost'] += sticker.get('generation_cost', 0)
            
            # Count categories
            category = sticker.get('category', 'unknown')
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
            
            # Count styles
            style = sticker.get('style', 'unknown')
            stats['styles'][style] = stats['styles'].get(style, 0) + 1
    
    return stats

def get_trending_stickers(limit: int = 20) -> List[Dict]:
    """
    Get trending stickers based on recent usage.
    
    Args:
        limit (int): Maximum number of stickers to return
        
    Returns:
        list: List of trending sticker dictionaries sorted by usage count
    """
    # Get recent public stickers from all categories
    recent_stickers = get_recent_stickers(limit * 3, is_public_only=True)  # Get more to sort by usage
    
    # Sort by usage count (descending)
    trending = sorted(recent_stickers, key=lambda x: x.get('usage_count', 0), reverse=True)
    
    return trending[:limit]

def search_stickers(query: str, limit: int = 50) -> List[Dict]:
    """
    Search stickers by query (searches in title, description, and tags).
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results
        
    Returns:
        list: List of matching sticker dictionaries
    """
    if not query or not isinstance(query, str):
        return []
    
    query = query.strip().lower()
    if not query:
        return []
    
    # Split query into words for tag searching
    query_words = query.split()
    
    # Search by tags first
    tag_results = search_stickers_by_tags(query_words, limit, is_public_only=True)
    
    # TODO: In a real implementation, you might want to also search title and description
    # This would require either additional GSI indexes or a more sophisticated search solution
    
    return tag_results 

def transfer_session_stickers_to_user(session_id: str, user_id: str) -> Dict:
    """
    Transfer stickers created during anonymous session to registered user.
    This is called when a user registers or logs in for the first time.
    
    Args:
        session_id (str): ID of the anonymous session
        user_id (str): ID of the newly registered user
        
    Returns:
        dict: Statistics about the transfer (count of transferred stickers)
    """
    if not session_id or not user_id:
        raise ValueError("Both session_id and user_id are required")
    
    # Verify user exists
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found")
    
    # Get stickers created with this session_id
    # Note: These stickers have session_id in the 'created_by' field
    stickers = get_stickers_by_user(session_id, limit=1000, include_inactive=False)
    
    if not stickers:
        # No stickers to transfer - this is normal
        return {
            'transferred_count': 0,
            'message': 'No stickers to transfer'
        }
    
    transferred_count = 0
    failed_transfers = []
    
    # Update each sticker to belong to the user instead of the session
    for sticker in stickers:
        try:
            # Verify the sticker still exists
            existing_sticker = get_sticker(sticker['id'])
            if not existing_sticker:
                logger.error(f"Sticker {sticker['id']} not found in database")
                failed_transfers.append(sticker['id'])
                continue
            
            # Prepare the update data
            update_data = {
                'created_by': user_id,
                'metadata': {
                    **sticker.get('metadata', {}),
                    'transferred_from_session': session_id,
                    'transfer_timestamp': int(time.time())
                }
            }
            
            # Update the created_by field from session_id to user_id
            updated_sticker = update_sticker(sticker['id'], update_data)
            
            if updated_sticker:
                transferred_count += 1
                logger.info(f"Successfully transferred sticker {sticker['id']} from session {session_id} to user {user_id}")
            else:
                failed_transfers.append(sticker['id'])
                logger.error(f"Failed to transfer sticker {sticker['id']}: update_sticker returned None")
                
        except Exception as e:
            logger.error(f"Error updating sticker {sticker['id']}: {str(e)}")
            failed_transfers.append(sticker['id'])
    
    result = {
        'transferred_count': transferred_count,
        'failed_count': len(failed_transfers),
        'message': f'Successfully transferred {transferred_count} stickers to user account'
    }
    
    if failed_transfers:
        result['failed_stickers'] = failed_transfers
        logger.warning(f"Failed to transfer {len(failed_transfers)} stickers for user {user_id}")
    
    logger.info(f"Transferred {transferred_count} stickers from session {session_id} to user {user_id}")
    return result