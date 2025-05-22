from flask import Blueprint, request, jsonify, session
import json
from decimal import Decimal
from datetime import datetime
from dynamodb_utils import (
    create_user, 
    get_user, 
    get_user_by_email, 
    generate_pin,
    store_login_pin,
    verify_login_pin,
    create_transaction,
    get_user_transactions
)
from utils import send_login_email
from config import INITIAL_COINS, BONUS_COINS

template_bp = Blueprint('template', __name__)

@template_bp.route('/add-to-template', methods=['POST'])
def add_to_template():
    data = request.json
    filename = data.get('filename', '')
    quantity = data.get('quantity', 1)  # Default quantity is 1
    
    if not filename:
        return jsonify({"error": "No sticker provided"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Check if sticker already exists in template
    existing_index = next((i for i, sticker in enumerate(template_stickers) 
                         if isinstance(sticker, dict) and sticker.get('filename') == filename), None)
    
    if existing_index is not None:
        # Update existing sticker quantity
        template_stickers[existing_index]['quantity'] += quantity
    else:
        # Add the new sticker to the template with quantity
        template_stickers.append({
            'filename': filename,
            'quantity': quantity
        })
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@template_bp.route('/update-quantity', methods=['POST'])
def update_quantity():
    data = request.json
    filename = data.get('filename', '')
    quantity = data.get('quantity', 1)
    
    if not filename:
        return jsonify({"error": "No sticker specified for update"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Find the sticker and update quantity
    for sticker in template_stickers:
        if isinstance(sticker, dict) and sticker.get('filename') == filename:
            sticker['quantity'] = max(1, quantity)  # Ensure quantity is at least 1
            break
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@template_bp.route('/get-template', methods=['GET'])
def get_template():
    template_stickers = session.get('template_stickers', [])
    return jsonify({
        "template_stickers": template_stickers
    })

@template_bp.route('/remove-from-template', methods=['POST'])
def remove_from_template():
    data = request.json
    filename = data.get('filename', '')
    
    if not filename:
        return jsonify({"error": "No sticker specified for removal"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Remove the sticker if it exists in the template
    template_stickers = [s for s in template_stickers 
                        if not (isinstance(s, dict) and s.get('filename') == filename)]
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@template_bp.route('/clear-template', methods=['POST'])
def clear_template():
    # Reset template to only include the default hat sticker
    # I want to clear the template and start fresh
    session['template_stickers'] = [] 
    
    return jsonify({
        "success": True,
        "template_stickers": session['template_stickers']
    })