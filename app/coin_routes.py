from flask import Blueprint, request, jsonify, session
import json
from decimal import Decimal
from datetime import datetime
from dynamodb_utils import (
    get_user,
    create_transaction,
    get_user_by_email,
    get_user_transactions
)
from config import INITIAL_COINS, BONUS_COINS, COIN_PACKAGES_CONFIG, STICKER_COSTS

coin_bp = Blueprint('coin', __name__)

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

@coin_bp.route('/api/coins/balance', methods=['GET'])
def get_coin_balance():
    """
    Get the current user's coin balance
    """
    user_id = session.get('user_id')
    
    if not user_id:
        # For non-authenticated users, ensure they have the default initial coins
        if 'coins' not in session:
            session['coins'] = INITIAL_COINS  # Default for non-authenticated users
        
        return jsonify({
            "coins": session.get('coins', INITIAL_COINS)
        })
    
    # For authenticated users, get from DynamoDB
    # Get latest user data
    user = get_user(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Sanitize data for JSON serialization
    user = sanitize_dynamodb_response(user)
    
    # Update session with latest coins
    session['coins'] = user.get('coins', 0)
    
    return jsonify({
        "coins": user.get('coins', 0)
    })

@coin_bp.route('/api/coins/purchase', methods=['POST'])
def purchase_coins():
    """
    Process a coin purchase
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    amount = data.get('amount')
    payment_id = data.get('payment_id')
    
    if not amount or not payment_id:
        return jsonify({"error": "Amount and payment_id are required"}), 400
    
    try:
        # Record the transaction (which also updates user's coins)
        transaction = create_transaction(
            user_id=user_id,
            coins_amount=amount,
            transaction_type='purchase',
            details={
                'payment_id': payment_id,
                'payment_method': data.get('payment_method', 'mercadopago')
            }
        )
        
        # Sanitize data for JSON serialization
        updated_user = transaction.get('updated_user', {})
        updated_user = sanitize_dynamodb_response(updated_user)
        transaction = sanitize_dynamodb_response(transaction)
        
        # Update session
        session['coins'] = updated_user.get('coins', 0)
        
        return jsonify({
            "success": True,
            "transaction_id": transaction['transaction_id'],
            "new_balance": updated_user.get('coins', 0)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to process purchase: {str(e)}"}), 500


@coin_bp.route('/api/coins/award', methods=['POST'])
def award_coins():
    """
    Award bonus coins to a user (admin only)
    """
    # TODO: Add proper admin authentication
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    email = data.get('email')
    amount = data.get('amount')
    reason = data.get('reason', 'Bonus award')
    
    if not email or not amount:
        return jsonify({"error": "Email and amount are required"}), 400
    
    try:
        # Get user by email
        user = get_user_by_email(email)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user = sanitize_dynamodb_response(user)
        
        # Record the transaction (which also updates user's coins)
        transaction = create_transaction(
            user_id=user['user_id'],
            coins_amount=amount,
            transaction_type='bonus',
            details={
                'reason': reason
            }
        )
        
        # Sanitize data for JSON serialization
        updated_user = transaction.get('updated_user', {})
        updated_user = sanitize_dynamodb_response(updated_user)
        transaction = sanitize_dynamodb_response(transaction)
        
        return jsonify({
            "success": True,
            "user_id": user['user_id'],
            "transaction_id": transaction['transaction_id'],
            "new_balance": updated_user.get('coins', 0)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to award coins: {str(e)}"}), 500

@coin_bp.route('/api/transactions', methods=['GET'])
def get_transactions():
    """
    Get transaction history for the current user
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    limit = request.args.get('limit', 50, type=int)
    
    try:
        transactions = get_user_transactions(user_id, limit=limit)
        
        # Sanitize data for JSON serialization
        transactions = sanitize_dynamodb_response(transactions)
        
        return jsonify({
            "transactions": transactions
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve transactions: {str(e)}"}), 500

@coin_bp.route('/api/coins/packages', methods=['GET'])
def get_coin_packages():
    """
    Get available coin packages for purchase
    """
    return jsonify({
        "packages": COIN_PACKAGES_CONFIG
    })

@coin_bp.route('/api/coins/purchase-package', methods=['POST'])
def purchase_coin_package():
    """
    Purchase a specific coin package
    """
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    package_id = data.get('package_id')
    payment_id = data.get('payment_id')
    
    if not package_id or not payment_id:
        return jsonify({"error": "Package ID and payment_id are required"}), 400
    
    # Validate package exists
    if package_id not in COIN_PACKAGES_CONFIG:
        return jsonify({"error": f"Invalid package ID: {package_id}"}), 400
    
    package = COIN_PACKAGES_CONFIG[package_id]
    coins_amount = package['coins']
    package_cost = package['price']  # Changed from 'cost' to 'price' to match COIN_PACKAGES_CONFIG structure
    
    try:
        # Record the transaction (which also updates user's coins)
        transaction = create_transaction(
            user_id=user_id,
            coins_amount=coins_amount,
            transaction_type='purchase',
            details={
                'payment_id': payment_id,
                'payment_method': data.get('payment_method', 'mercadopago'),
                'package_id': package_id,
                'package_cost': package_cost,
                'currency_id': package.get('currency_id', 'ARS')  # Added currency_id from COIN_PACKAGES_CONFIG
            }
        )
        
        # Sanitize data for JSON serialization
        updated_user = transaction.get('updated_user', {})
        updated_user = sanitize_dynamodb_response(updated_user)
        transaction = sanitize_dynamodb_response(transaction)
        
        # Update session
        session['coins'] = updated_user.get('coins', 0)
        
        return jsonify({
            "success": True,
            "transaction_id": transaction['transaction_id'],
            "new_balance": updated_user.get('coins', 0),
            "package": package_id,
            "coins_added": coins_amount,
            "package_name": package.get('name')  # Added package name to response
        })
    except Exception as e:
        return jsonify({"error": f"Failed to process package purchase: {str(e)}"}), 500

@coin_bp.route('/api/stickers/costs', methods=['GET'])
def get_sticker_costs():
    """
    Get the costs for generating stickers at different quality levels
    """
    return jsonify({
        "costs": STICKER_COSTS
    }) 