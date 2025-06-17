"""
Sticker Routes - HTTP endpoints for sticker management
"""
from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps
import logging
from typing import Dict, Any

# Import services
from services.sticker_services import (
    create_user_sticker, create_library_sticker, get_sticker_gallery,
    use_sticker, update_sticker_details, delete_user_sticker,
    get_user_sticker_stats, get_trending_stickers, search_stickers,
    StickerValidationError
)
from models.stickers_models import (
    get_sticker, get_stickers_by_user, get_public_stickers,
    get_recent_stickers, get_stickers_by_category
)
from utils.dynamodb_utils import get_user

# Create blueprint
sticker_bp = Blueprint('stickers', __name__, url_prefix='/api/stickers')

# Set up logging
logger = logging.getLogger(__name__)

def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = get_user(session['user_id'])
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def handle_errors(f):
    """Decorator for error handling"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except StickerValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except ValueError as e:
            logger.error(f"Value error: {str(e)}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function

# Public Routes

@sticker_bp.route('/gallery', methods=['GET'])
@handle_errors
def get_stickers():
    """
    Get stickers for public gallery with filters
    Query params:
    - category: Filter by category
    - style: Filter by style  
    - tags: Comma-separated list of tags
    - limit: Max number of results (default 50)
    - user_id: Get stickers from specific user (optional)
    """
    category = request.args.get('category')
    style = request.args.get('style')
    tags_str = request.args.get('tags')
    limit = int(request.args.get('limit', 50))
    user_id = request.args.get('user_id')
    
    # Parse tags
    tags = None
    if tags_str:
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
    
    # Get stickers
    stickers = get_sticker_gallery(
        category=category,
        style=style,
        tags=tags,
        user_id=user_id,
        limit=limit
    )
    
    return jsonify({
        'stickers': stickers,
        'count': len(stickers),
        'filters': {
            'category': category,
            'style': style,
            'tags': tags,
            'user_id': user_id
        }
    })

@sticker_bp.route('/recent', methods=['GET'])
@handle_errors
def get_recent():
    """
    Get recent stickers
    Query params:
    - limit: Max number of results (default 20)
    - category: Filter by category (optional)
    """
    limit = int(request.args.get('limit', 20))
    category = request.args.get('category')
    
    stickers = get_recent_stickers(limit=limit, is_public_only=True, category=category)
    
    return jsonify({
        'stickers': stickers,
        'count': len(stickers)
    })

@sticker_bp.route('/trending', methods=['GET'])
@handle_errors
def get_trending():
    """
    Get trending stickers based on usage
    Query params:
    - limit: Max number of results (default 20)
    """
    limit = int(request.args.get('limit', 20))
    
    stickers = get_trending_stickers(limit=limit)
    
    return jsonify({
        'stickers': stickers,
        'count': len(stickers)
    })

@sticker_bp.route('/search', methods=['GET'])
@handle_errors
def search():
    """
    Search stickers by query
    Query params:
    - q: Search query (required)
    - limit: Max number of results (default 50)
    """
    query = request.args.get('q')
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    limit = int(request.args.get('limit', 50))
    
    stickers = search_stickers(query=query, limit=limit)
    
    return jsonify({
        'stickers': stickers,
        'count': len(stickers),
        'query': query
    })

@sticker_bp.route('/<sticker_id>', methods=['GET'])
@handle_errors
def get_sticker_by_id(sticker_id):
    """Get a specific sticker by ID"""
    sticker = get_sticker(sticker_id)
    
    if not sticker:
        return jsonify({'error': 'Sticker not found'}), 404
    
    return jsonify({'sticker': sticker})

@sticker_bp.route('/<sticker_id>/use', methods=['POST'])
@handle_errors
def mark_sticker_used(sticker_id):
    """Mark a sticker as used (increment usage count)"""
    user_id = session.get('user_id')  # Optional - can track usage without login
    
    success, sticker = use_sticker(sticker_id, user_id)
    
    if not success:
        return jsonify({'error': 'Failed to mark sticker as used'}), 400
    
    return jsonify({
        'message': 'Sticker usage recorded',
        'sticker': sticker
    })

# User-specific Routes (require login)

@sticker_bp.route('/my-stickers', methods=['GET'])
@login_required
@handle_errors
def get_my_stickers():
    """
    Get current user's stickers
    Query params:
    - limit: Max number of results (default 50)
    - include_inactive: Include deleted stickers (default false)
    """
    user_id = session['user_id']
    limit = int(request.args.get('limit', 50))
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    stickers = get_stickers_by_user(user_id, limit=limit, include_inactive=include_inactive)
    
    return jsonify({
        'stickers': stickers,
        'count': len(stickers)
    })

@sticker_bp.route('/my-stats', methods=['GET'])
@login_required
@handle_errors
def get_my_stats():
    """Get current user's sticker statistics"""
    user_id = session['user_id']
    
    stats = get_user_sticker_stats(user_id)
    
    return jsonify({'stats': stats})

@sticker_bp.route('/', methods=['POST'])
@login_required
@handle_errors
def create_sticker():
    """
    Create a new sticker
    Body:
    - image_url: URL of the sticker image (required)
    - image_url_high: URL of high res image (optional)
    - title: Title of the sticker (optional)
    - description: Description (optional)
    - tags: Array of tags (optional)
    - is_public: Whether sticker is public (default true)
    - style: Style used (optional)
    - generation_cost: Cost in coins (default 0)
    - prompt: Original prompt (optional)
    - metadata: Additional metadata (optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('image_url'):
        return jsonify({'error': 'image_url is required'}), 400
    
    user_id = session['user_id']
    
    sticker = create_user_sticker(
        user_id=user_id,
        image_url=data['image_url'],
        image_url_high=data.get('image_url_high'),
        title=data.get('title'),
        description=data.get('description'),
        tags=data.get('tags'),
        is_public=data.get('is_public', True),
        style=data.get('style'),
        generation_cost=data.get('generation_cost', 0),
        prompt=data.get('prompt'),
        metadata=data.get('metadata')
    )
    
    return jsonify({
        'message': 'Sticker created successfully',
        'sticker': sticker
    }), 201

@sticker_bp.route('/<sticker_id>', methods=['PUT'])
@login_required
@handle_errors
def update_sticker(sticker_id):
    """
    Update a sticker
    Body can include: title, description, tags, is_public, style
    Only the creator or admin can update
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    user_id = session['user_id']
    
    updated_sticker = update_sticker_details(sticker_id, user_id, data)
    
    return jsonify({
        'message': 'Sticker updated successfully',
        'sticker': updated_sticker
    })

@sticker_bp.route('/<sticker_id>', methods=['DELETE'])
@login_required
@handle_errors
def delete_sticker(sticker_id):
    """
    Delete a sticker (soft delete by default)
    Query params:
    - hard: Set to 'true' for hard delete (admin only)
    Only the creator or admin can delete
    """
    user_id = session['user_id']
    hard_delete = request.args.get('hard', 'false').lower() == 'true'
    
    # For hard delete, require admin
    if hard_delete:
        user = get_user(user_id)
        if not user or user.get('role') != 'admin':
            return jsonify({'error': 'Admin privileges required for hard delete'}), 403
    
    success = delete_user_sticker(sticker_id, user_id, hard_delete=hard_delete)
    
    if not success:
        return jsonify({'error': 'Failed to delete sticker'}), 400
    
    delete_type = 'hard deleted' if hard_delete else 'deleted'
    return jsonify({'message': f'Sticker {delete_type} successfully'})

# Admin Routes

@sticker_bp.route('/admin/library', methods=['POST'])
@admin_required
@handle_errors
def create_library_sticker():
    """
    Create a library sticker (admin only)
    Body:
    - image_url: URL of the sticker image (required)
    - image_url_high: URL of high res image (optional)
    - title: Title of the sticker (required)
    - description: Description (optional)
    - tags: Array of tags (optional)
    - style: Style (optional)
    - metadata: Additional metadata (optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400
    
    if not data.get('image_url'):
        return jsonify({'error': 'image_url is required'}), 400
    
    if not data.get('title'):
        return jsonify({'error': 'title is required for library stickers'}), 400
    
    sticker = create_library_sticker(
        image_url=data['image_url'],
        title=data['title'],
        image_url_high=data.get('image_url_high'),
        description=data.get('description'),
        tags=data.get('tags'),
        style=data.get('style'),
        metadata=data.get('metadata')
    )
    
    return jsonify({
        'message': 'Library sticker created successfully',
        'sticker': sticker
    }), 201

@sticker_bp.route('/admin/categories', methods=['GET'])
@admin_required
@handle_errors
def get_categories():
    """Get stickers grouped by category (admin only)"""
    categories = {}
    
    # Get stickers from each main category
    for category in ['user_generated', 'library', 'template']:
        stickers = get_stickers_by_category(category, limit=100, is_public_only=False)
        categories[category] = {
            'stickers': stickers,
            'count': len(stickers)
        }
    
    return jsonify({'categories': categories})

@sticker_bp.route('/admin/user/<user_id>/stats', methods=['GET'])
@admin_required
@handle_errors
def get_user_stats_admin(user_id):
    """Get any user's sticker statistics (admin only)"""
    stats = get_user_sticker_stats(user_id)
    
    return jsonify({'stats': stats, 'user_id': user_id})
