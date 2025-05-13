from flask import Blueprint, request, jsonify, session
import os
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
    
    # Generate a PIN
    pin = generate_pin()
    
    # Store PIN in DynamoDB with expiration
    success = store_login_pin(email, pin, expiry_seconds=600)  # 10 minutes expiry
    
    if not success:
        return jsonify({"error": "Failed to store login PIN"}), 500
    
    # Send PIN via email
    try:
        send_login_email(email, pin)
        return jsonify({"success": True, "message": "Login PIN sent to your email"})
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

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
    
    # Set user in session
    session['user_id'] = user['user_id']
    session['email'] = user['email']
    session['coins'] = user.get('coins', 0)
    
    return jsonify({
        "success": True,
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "coins": user.get('coins', 0)
        }
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """
    Log the user out by clearing their session
    """
    # Clear user data from session
    session.pop('user_id', None)
    session.pop('email', None)
    session.pop('coins', None)
    
    return jsonify({"success": True})

@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """
    Get the current logged-in user information
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get full user data from DynamoDB
    user = get_user(user_id)
    
    if not user:
        # Clear invalid session
        session.pop('user_id', None)
        session.pop('email', None)
        session.pop('coins', None)
        return jsonify({"error": "User not found"}), 404
    
    # Convert any Decimal values to float
    user = sanitize_dynamodb_response(user)
    
    # Update session with latest data
    session['coins'] = user.get('coins', 0)
    
    return jsonify({
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "coins": user.get('coins', 0),
            "created_at": user.get('created_at'),
            "last_login": user.get('last_login')
        }
    }) 