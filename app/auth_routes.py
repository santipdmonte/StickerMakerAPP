from flask import Blueprint, request, jsonify, session
import json
from decimal import Decimal
from datetime import datetime
from dynamodb_utils import (
    create_user, 
    get_user, 
    get_user_by_email, 
    update_user_coins,
    generate_pin,
    store_login_pin,
    verify_login_pin,
    create_transaction,
    get_user_transactions
)
from utils import send_login_email
from config import INITIAL_COINS, BONUS_COINS

auth_bp = Blueprint('auth', __name__)

# Helper function to convert DynamoDB Decimal values
def sanitize_dynamodb_response(data):
    """Convert DynamoDB response to JSON-serializable format"""
    if isinstance(data, dict):
        return {k: sanitize_dynamodb_response(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_dynamodb_response(v) for v in data]
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data

@auth_bp.route('/api/auth/request-login', methods=['POST'])
def request_login():
    """
    Request a login PIN to be sent to the user's email
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    # Check if user exists with this email
    user = get_user_by_email(email)
    
    # Generate a PIN
    pin = generate_pin()
    
    # Store PIN in DynamoDB with expiration
    # If user exists, send the PIN; if not, return that user doesn't exist
    success, user_exists = store_login_pin(email, pin, expiry_seconds=600)  # 10 minutes expiry
    
    if not success:
        return jsonify({"error": "Failed to store login PIN"}), 500
    
    if user_exists:
        # Existing user - send PIN via email
        try:
            send_login_email(email, pin)
            return jsonify({
                "success": True, 
                "user_exists": True,
                "message": "Login PIN sent to your email"
            })
        except Exception as e:
            return jsonify({"error": f"Failed to send email: {str(e)}"}), 500
    else:
        # New user - ask for name
        return jsonify({
            "success": True,
            "user_exists": False,
            "message": "User not found. Please provide your name to create an account."
        })

@auth_bp.route('/api/auth/verify-pin', methods=['POST'])
def verify_pin():
    """
    Verify a login PIN and authenticate the user
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    email = data.get('email')
    pin = data.get('pin')
    
    if not email or not pin:
        return jsonify({"error": "Email and PIN are required"}), 400
    
    # Verify the PIN
    user = verify_login_pin(email, pin)
    
    if not user:
        return jsonify({"error": "Invalid or expired PIN"}), 401
    
    # Convert any Decimal values before using in session
    user = sanitize_dynamodb_response(user)
    
    # Check if this is a newly created user (created during PIN verification)
    is_new_user = user.get('is_new_user', False)
    
    # Handle coins based on whether this is a new user or existing user
    if is_new_user:
        # For a new user: add bonus coins from registration bonus to their current session coins
        current_session_coins = int(session.get('coins', 0))
        
        # Ensure user coins is treated as an integer
        user_current_coins = int(float(user.get('coins', 0)))
        
        # Compute coins to add (session coins + bonus - current coins)
        # This ensures we add exactly enough to reach session coins + bonus
        coins_to_add = (current_session_coins + BONUS_COINS) - user_current_coins
        
        # Update user in DynamoDB with the additional coins
        try:
            user = update_user_coins(user['user_id'], coins_to_add)
            user = sanitize_dynamodb_response(user)
        except Exception as e:
            return jsonify({"error": f"Failed to update coins: {str(e)}"}), 500
    
    # Set the session as permanent so it persists beyond browser close
    session.permanent = True
    
    # Set user in session
    session['user_id'] = user['user_id']
    session['email'] = user['email']
    session['coins'] = user.get('coins', 0)
    if 'name' in user:
        session['name'] = user['name']
    
    # Create response with session data
    response = jsonify({
        "success": True,
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "name": user.get('name', ''),
            "coins": user.get('coins', 0),
            "is_new_user": is_new_user
        }
    })
    
    # Set additional cookies to ensure persistence
    max_age = 30 * 24 * 60 * 60  # 30 days in seconds
    # Store user info in cookie as backup
    response.set_cookie('auth_user_id', user['user_id'], max_age=max_age, httponly=True, samesite='Lax')
    response.set_cookie('auth_email', user['email'], max_age=max_age, httponly=True, samesite='Lax')
    
    return response

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """
    Log the user out by clearing their session
    """
    # Clear user data from session
    session.pop('user_id', None)
    session.pop('email', None)
    session.pop('coins', None)
    session.pop('name', None)
    
    # Also clear cookies
    response = jsonify({"success": True})
    response.set_cookie('auth_user_id', '', expires=0)
    response.set_cookie('auth_email', '', expires=0)
    
    return response

@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """
    Get the current logged-in user information
    """
    user_id = session.get('user_id')
    
    # If no user_id in session, check the backup cookie
    if not user_id:
        # Try to get user_id from cookie
        cookie_user_id = request.cookies.get('auth_user_id')
        if cookie_user_id:
            user_id = cookie_user_id
            # Restore session from cookie
            cookie_email = request.cookies.get('auth_email')
            session['user_id'] = user_id
            if cookie_email:
                session['email'] = cookie_email
        else:
            return jsonify({"error": "Not authenticated"}), 401
    
    # Get full user data from DynamoDB
    user = get_user(user_id)
    
    if not user:
        # Clear invalid session
        session.pop('user_id', None)
        session.pop('email', None)
        session.pop('coins', None)
        session.pop('name', None)
        # Clear cookies too
        response = jsonify({"error": "User not found"}), 404
        response[0].set_cookie('auth_user_id', '', expires=0)
        response[0].set_cookie('auth_email', '', expires=0)
        return response
    
    # Convert any Decimal values to float
    user = sanitize_dynamodb_response(user)
    
    # Update session with latest data
    session['user_id'] = user['user_id']
    session['email'] = user['email']
    session['coins'] = user.get('coins', 0)
    if 'name' in user:
        session['name'] = user['name']
    
    return jsonify({
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "name": user.get('name', ''),
            "coins": user.get('coins', 0),
            "created_at": user.get('created_at'),
            "last_login": user.get('last_login')
        }
    })

@auth_bp.route('/api/auth/create-account', methods=['POST'])
def create_account():
    """
    Create a new user account with name and send login PIN
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    email = data.get('email')
    name = data.get('name')
    
    if not email or not name:
        return jsonify({"error": "Email and name are required"}), 400
    
    # Check if user already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return jsonify({
            "error": "User with this email already exists",
            "user_exists": True
        }), 400
    
    # Create new user with name
    user = create_user(email, INITIAL_COINS + BONUS_COINS, name)
    
    # Generate and store PIN
    pin = generate_pin()
    success, _ = store_login_pin(email, pin, expiry_seconds=600, create_if_not_exists=False)  # User already created
    
    if not success:
        return jsonify({"error": "Failed to store login PIN"}), 500
    
    # Send PIN via email
    try:
        send_login_email(email, pin, name)
        return jsonify({
            "success": True,
            "message": "Account created successfully. Login PIN sent to your email.",
            "user": {
                "email": email,
                "name": name
            }
        })
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500 