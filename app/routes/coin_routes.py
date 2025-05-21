from flask import Blueprint, request, jsonify, session, url_for, current_app
import json
import uuid
import time
from decimal import Decimal
from datetime import datetime
from dynamodb_utils import (
    get_user,
    create_transaction,
    get_user_by_email,
    get_user_transactions
)
from config import INITIAL_COINS, BONUS_COINS, COIN_PACKAGES_CONFIG, STICKER_COSTS, sdk

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
    
@coin_bp.route('/get-coins', methods=['GET'])
def get_coins():
    """
    Return current coin balance from the session or DB
    """
    user_id = session.get('user_id')
    
    if user_id:
        # Get latest user data from DB
        user = get_user(user_id)
        if user:
            # Update session with latest coins
            session['coins'] = user.get('coins', 0)
    
    # Make sure coins is set in the session (for non-authenticated users)
    if 'coins' not in session:
        session['coins'] = INITIAL_COINS  # Default for non-authenticated users
        
        # Asegurarnos de que haya un session_id para visitantes anónimos
        if not user_id and 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
    
    # Return current coin balance from session
    return jsonify({"coins": session.get('coins', INITIAL_COINS)})

@coin_bp.route('/update-coins', methods=['POST'])
def update_coins():
    """
    Update coin balance in the session and DynamoDB if enabled
    """
    coins_update = request.json.get('coins', 0)
    
    if coins_update == 0:
        return jsonify({"coins": session.get('coins', 0)})
    
    user_id = session.get('user_id')
    
    if user_id:
        try:
            # Determine transaction type based on whether we're adding or removing coins
            transaction_type = 'usage' if coins_update < 0 else 'bonus'
            
            # Record transaction (which also updates the user's coins)
            transaction = create_transaction(
                user_id=user_id,
                coins_amount=coins_update,
                transaction_type=transaction_type,
                details={'source': 'app', 'api_route': '/update-coins'}
            )
            
            # Update session with latest coins
            updated_user = transaction.get('updated_user', {})
            if updated_user:
                session['coins'] = updated_user.get('coins', 0)
        except Exception as e:
            print(f"Error updating coins in DynamoDB: {e}")
            # Fall back to session-based coins
            current_coins = session.get('coins', 0)
            session['coins'] = max(0, current_coins + coins_update)
    else:
        # Visitante anónimo - asegurarnos de que tenga session_id
        if not user_id and 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            
        # Session-based coin handling for anonymous users
        current_coins = session.get('coins', 0)
        session['coins'] = max(0, current_coins + coins_update)
        
        # Log transaction for anonymous users
        identifier = session.get('session_id') if not user_id else user_id
        current_app.logger.info(f"Anonymous user (session_id: {identifier}) coin update: {coins_update}, new balance: {session['coins']}")
    
    return jsonify({"coins": session.get('coins', 0)})

@coin_bp.route('/purchase-coins', methods=['POST'])
def purchase_coins():
    """
    Procesa una solicitud de compra de monedas.
    Requiere que el usuario esté autenticado y proporcione un package_id válido.
    """
    current_app.logger.info("--- /purchase-coins ---")

    if not request.is_json:
        current_app.logger.error("Request is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.json
    
    user_id = session.get('user_id')

    if not user_id:
        current_app.logger.error("No user_id in session, se requiere autenticación para comprar monedas")
        return jsonify({"error": "Debes iniciar sesión para comprar monedas"}), 401
    
    # Coin Package Purchase (Initiate Mercado Pago payment)
    package_id = data.get('package_id')
    current_app.logger.info(f"Solicitud de compra de monedas iniciada para package_id: {package_id} por usuario: {user_id}")

    if not package_id or package_id not in COIN_PACKAGES_CONFIG:
        current_app.logger.error(f"Invalid or missing package_id: {package_id}")
        return jsonify({"error": "Paquete de monedas inválido o no especificado"}), 400

    package_info = COIN_PACKAGES_CONFIG[package_id]
    
    payer_info = {}
    
    # Obtener información del usuario de la base de datos
    db_user = get_user(user_id)
    if not db_user:
        current_app.logger.error(f"Usuario {user_id} no encontrado en la base de datos")
        return jsonify({"error": "Error al recuperar datos del usuario"}), 400
        
    payer_info['email'] = db_user.get('email', '')
    if db_user.get('name'):
        payer_info['name'] = db_user.get('name')

    if not sdk:
        current_app.logger.error("Mercado Pago SDK not configured for coin purchase")
        return jsonify({"error": "El sistema de pagos no está configurado correctamente"}), 500

    try:
        timestamp = int(time.time())
        # External reference: Type_UserID_PackageID_Coins_Timestamp
        external_reference = f"COINPKG_{user_id}_{package_id}_{package_info['coins']}_{timestamp}"

        preference_data = {
            "items": [{
                "title": package_info['name'],
                "description": f"{package_info['coins']} monedas virtuales para TheStickerHouse",
                "quantity": 1,
                "unit_price": package_info['price'],
                "currency_id": package_info['currency_id']
            }],
            "payer": payer_info,
            "back_urls": {
                "success": url_for('payment.coin_payment_feedback', _external=True, _scheme='https'),
                "failure": url_for('payment.coin_payment_feedback', _external=True, _scheme='https'),
                "pending": url_for('payment.coin_payment_feedback', _external=True, _scheme='https')
            },
            "auto_return": "approved",
            "external_reference": external_reference,
            "notification_url": url_for('payment.webhook', _external=True, _scheme='https')
        }
        
        current_app.logger.info(f"Creando preferencia de Mercado Pago. Ref: {external_reference}")
        preference_response = sdk.preference().create(preference_data)

        if preference_response and isinstance(preference_response, dict) and \
            preference_response.get("status") in [200, 201] and \
            preference_response.get("response") and "id" in preference_response["response"]:
            preference_id = preference_response["response"]["id"]
            current_app.logger.info(f"Preferencia creada exitosamente con ID: {preference_id}")
            return jsonify({"preference_id": preference_id})
        else:
            error_message = "Error al crear la preferencia de pago con Mercado Pago"
            if preference_response and isinstance(preference_response, dict) and preference_response.get("response"):
                error_message = preference_response["response"].get("message", error_message)
            elif preference_response and isinstance(preference_response, dict) and preference_response.get("message"):
                error_message = preference_response.get("message", error_message)
            current_app.logger.error(f"Error en creación de preferencia: {error_message}")
            return jsonify({"error": error_message}), 500
    except Exception as e:
        current_app.logger.error(f"Excepción creando preferencia de pago: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error crítico al procesar el pago: {str(e)}"}), 500

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
def purchase_coins_api():
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