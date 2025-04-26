import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import time
import json
from dotenv import load_dotenv

# Added Mercado Pago
import mercadopago 

from generate_sticker import generate_sticker, generate_sticker_with_reference
from utils import create_placeholder_image

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure Flask from environment variables
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default_secret_key') 
# app.config['SERVER_NAME'] = os.getenv('FLASK_SERVER_NAME', None) # REMOVED: Let url_for infer from request

# TheStickerHouse - Sticker generation web application

# Configure Mercado Pago SDK
mp_access_token = os.getenv("PROD_ACCESS_TOKEN")
if not mp_access_token:
    print("Error: PROD_ACCESS_TOKEN not found in .env file.")
    # Handle the error appropriately, maybe raise an exception or use a default test token
    # For demonstration, let's allow it to continue but it won't work without a token
sdk = mercadopago.SDK(mp_access_token) if mp_access_token else None

# Create imgs/ folder
folder_path = "app/static/imgs"
os.makedirs(folder_path, exist_ok=True)


@app.route('/')
def index():
    # Initialize empty template if not exists in session or convert old format to new format
    if 'template_stickers' not in session:
        session['template_stickers'] = [{'filename': 'hat.png', 'quantity': 1}]
    else:
        # Convert any string items to object format for backward compatibility
        template_stickers = session['template_stickers']
        updated_stickers = []
        for sticker in template_stickers:
            if isinstance(sticker, str):
                updated_stickers.append({'filename': sticker, 'quantity': 1})
            else:
                updated_stickers.append(sticker)
        session['template_stickers'] = updated_stickers
    
    # Initialize coins if not exists in session
    if 'coins' not in session:
        session['coins'] = 100  # Start with 100 coins for new users
    
    # Get the Mercado Pago public key from environment variables
    mp_public_key = os.getenv('MP_PUBLIC_KEY', '')
        
    return render_template('index.html', mp_public_key=mp_public_key)


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', '')
    quality = data.get('quality', 'low')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    # Generate a unique filename based on timestamp
    timestamp = int(time.time())
    filename = f"sticker_{timestamp}.png"
    img_path = os.path.join(folder_path, filename)
    
    try:
        image_b64 = generate_sticker(prompt, img_path, quality)
        # image_b64 = create_placeholder_image(img_path)
        
        return jsonify({"success": True, "filename": filename, "image": image_b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate-with-reference', methods=['POST'])
def generate_with_reference():
    data = request.json
    prompt = data.get('prompt', '')
    reference_image = data.get('referenceImage', '')
    quality = data.get('quality', 'low')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    if not reference_image:
        return jsonify({"error": "No reference image provided"}), 400
    
    # Generate a unique filename based on timestamp
    timestamp = int(time.time())
    filename = f"sticker_{timestamp}.png"
    img_path = os.path.join(folder_path, filename)
    
    try:
        image_b64 = generate_sticker_with_reference(prompt, img_path, reference_image, quality)
        # image_b64 = create_placeholder_image(img_path)
        
        return jsonify({"success": True, "filename": filename, "image": image_b64})
    except ValueError as e:
        return jsonify({"error": f"Invalid image format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add-to-template', methods=['POST'])
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

@app.route('/update-quantity', methods=['POST'])
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

@app.route('/get-template', methods=['GET'])
def get_template():
    template_stickers = session.get('template_stickers', [])
    return jsonify({
        "template_stickers": template_stickers
    })

@app.route('/remove-from-template', methods=['POST'])
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

@app.route('/clear-template', methods=['POST'])
def clear_template():
    # Reset template to only include the default hat sticker
    session['template_stickers'] = [{'filename': 'hat.png', 'quantity': 1}]
    
    return jsonify({
        "success": True,
        "template_stickers": session['template_stickers']
    })

@app.route('/get-library', methods=['GET'])
def get_library():
    # Get all sticker files from the imgs directory
    sticker_files = []
    try:
        for file in os.listdir(folder_path):
            if file.endswith('.png'):
                sticker_files.append(file)
        return jsonify({
            "success": True,
            "stickers": sticker_files
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Coins System Routes ---

@app.route('/get-coins', methods=['GET'])
def get_coins():
    # Return current coin balance
    coins = session.get('coins', 0)
    return jsonify({
        "success": True,
        "coins": coins
    })

@app.route('/update-coins', methods=['POST'])
def update_coins():
    data = request.json
    amount = data.get('amount', 0)
    
    # Get current coins from session
    current_coins = session.get('coins', 0)
    
    # Update coins
    new_coins = max(0, current_coins + amount)
    session['coins'] = new_coins
    
    return jsonify({
        "success": True,
        "coins": new_coins
    })

@app.route('/purchase-coins', methods=['POST'])
def purchase_coins():
    if not sdk:
        return jsonify({"error": "Mercado Pago SDK not configured. Check Access Token."}), 500
         
    data = request.json
    name = data.get('name')
    email = data.get('email')
    coin_package = data.get('package')
    
    if not all([name, email, coin_package]):
        return jsonify({"error": "Missing required information for purchase."}), 400

    # Define coin packages with their prices and amounts
    coin_packages = {
        "small": {"amount": 100, "price": 500.00},
        "medium": {"amount": 300, "price": 1000.00},
        "large": {"amount": 500, "price": 1500.00}
    }
    
    if coin_package not in coin_packages:
        return jsonify({"error": "Invalid coin package selected."}), 400
    
    package_info = coin_packages[coin_package]
    
    items = [{
        "title": f"{package_info['amount']} Coins Package",
        "quantity": 1,
        "unit_price": package_info['price'],
        "currency_id": "ARS" # Or your country's currency code
    }]
    
    total_amount = package_info['price']
    
    # Basic payer info
    payer = {
        "name": name,
        "email": email
    }

    # Define back URLs dynamically using url_for
    base_url = request.url_root
    
    try:
        # Force HTTPS scheme for external URLs
        success_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package)
        failure_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package)
        pending_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package)
        
        back_urls_data = {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url
        }
        
    except Exception as url_gen_err:
        print(f"Error generating back URLs: {url_gen_err}")
        return jsonify({"error": f"Failed to generate callback URLs: {str(url_gen_err)}"}), 500

    preference_data = {
        "items": items,
        "payer": payer,
        "back_urls": back_urls_data,
        "auto_return": "approved",
    }
    
    try:
        preference_response = sdk.preference().create(preference_data)

        if preference_response and isinstance(preference_response, dict) and preference_response.get("status") in [200, 201] and "response" in preference_response and "id" in preference_response["response"]:
            preference = preference_response["response"]
            return jsonify({
                "success": True,
                "preference_id": preference['id'],
                "package": coin_package,
                "amount": package_info['amount']
            })
        else:
            error_message = "Failed to create payment preference due to unexpected response."
            if preference_response and isinstance(preference_response, dict) and "response" in preference_response and "message" in preference_response["response"]:
                error_message = f"Mercado Pago Error: {preference_response['response']['message']}"
            elif preference_response and isinstance(preference_response, dict) and "message" in preference_response:
                 error_message = f"Mercado Pago Error: {preference_response['message']}"
                 
            return jsonify({"error": error_message}), 500
            
    except Exception as e:
        print(f"Error creating preference: {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_detail = e.response.text
             except:
                 pass
        return jsonify({"error": f"Failed to create payment preference: {error_detail}"}), 500

@app.route('/coin_payment_feedback')
def coin_payment_feedback():
    # Handle the user returning from Mercado Pago
    status = request.args.get('status')
    payment_id = request.args.get('payment_id')
    coin_package = request.args.get('package')
    
    # Define coin packages with their amounts
    coin_packages = {
        "small": 100,
        "medium": 300,
        "large": 500
    }
    
    if status == 'approved' and coin_package in coin_packages:
        # Add coins to user's account
        current_coins = session.get('coins', 0)
        session['coins'] = current_coins + coin_packages[coin_package]
        
    # Redirect back to index
    return redirect(url_for('index'))

# --- End Coins System Routes ---

# --- Mercado Pago Integration ---

@app.route('/create_preference', methods=['POST'])
def create_preference():
    if not sdk:
         return jsonify({"error": "Mercado Pago SDK not configured. Check Access Token."}), 500
         
    data = request.json
    name = data.get('name')
    email = data.get('email')
    # address = data.get('address') # Address isn't directly used in preference here, but good to have

    if not all([name, email]):
         return jsonify({"error": "Missing name or email for checkout."}), 400

    template_stickers = session.get('template_stickers', [])
    if not template_stickers:
        return jsonify({"error": "Template is empty. Cannot create preference."}), 400

    items = []
    total_amount = 0
    for sticker in template_stickers:
        # --- IMPORTANT: Define your actual pricing logic here ---
        # This is just a placeholder price. You need to set the real price per sticker.
        unit_price = 10.00 # Example: $10 per sticker
        # ---
        
        items.append({
            "title": f"Sticker - {sticker.get('filename', 'Unknown')}",
            "quantity": sticker.get('quantity', 1),
            "unit_price": unit_price,
            "currency_id": "ARS" # Or your country's currency code (e.g., BRL, MXN)
        })
        total_amount += sticker.get('quantity', 1) * unit_price

    # Basic payer info
    payer = {
        "name": name,
        "email": email
        # You can add more payer details if needed (phone, identification, address)
        # "address": { "street_name": address ... } 
    }

    # Define back URLs dynamically using url_for
    # Ensure your server is accessible externally for Mercado Pago callbacks
    base_url = request.url_root # Gets the base URL (e.g., http://127.0.0.1:5000/)
    
    # --- Generate Back URLs ---
    try:
        # Force HTTPS scheme for external URLs
        success_url = url_for('payment_feedback', _external=True, _scheme='https')
        failure_url = url_for('payment_feedback', _external=True, _scheme='https')
        pending_url = url_for('payment_feedback', _external=True, _scheme='https')
        
        back_urls_data = {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url
        }
        # Log the generated URLs
        print(f"Generated Back URLs (Forced HTTPS): {back_urls_data}") 
        
    except Exception as url_gen_err:
        print(f"Error generating back URLs: {url_gen_err}")
        return jsonify({"error": f"Failed to generate callback URLs: {str(url_gen_err)}"}), 500
    # --- End Generate Back URLs ---

    preference_data = {
        "items": items,
        "payer": payer,
        "back_urls": back_urls_data, # Use the generated dict
        "auto_return": "approved", # Automatically return for approved payments
        # "notification_url": url_for('webhook_receiver', _external=True) # Optional: For server-side notifications (IPN/Webhooks)
    }
    
    # --- Enhanced Logging ---
    print("--- Creating Preference ---")
    print("Preference Data Sent:")
    try:
        print(json.dumps(preference_data, indent=2))
    except Exception as json_err:
        print(f"(Could not serialize preference_data for logging: {json_err})")
        print(preference_data) # Print raw if JSON fails
    print("-------------------------")
    # --- End Enhanced Logging ---
    
    try:
        preference_response = sdk.preference().create(preference_data)
        
        # --- Enhanced Logging ---
        print("Preference Response Received:")
        try:
            print(json.dumps(preference_response, indent=2))
        except Exception as json_err:
            print(f"(Could not serialize preference_response for logging: {json_err})")
            print(preference_response) # Print raw if JSON fails
        print("-------------------------")
        # --- End Enhanced Logging ---

        # Check if response structure is as expected before accessing keys
        if preference_response and isinstance(preference_response, dict) and preference_response.get("status") in [200, 201] and "response" in preference_response and "id" in preference_response["response"]:
            preference = preference_response["response"]
            print(f"Successfully Created Preference ID: {preference['id']}") 
            return jsonify({"preference_id": preference['id']})
        else:
            # Log unexpected response structure
            print("Error: Unexpected response structure from Mercado Pago SDK.")
            error_message = "Failed to create payment preference due to unexpected response."
            if preference_response and isinstance(preference_response, dict) and "response" in preference_response and "message" in preference_response["response"]:
                error_message = f"Mercado Pago Error: {preference_response['response']['message']}"
            elif preference_response and isinstance(preference_response, dict) and "message" in preference_response:
                 error_message = f"Mercado Pago Error: {preference_response['message']}"
                 
            return jsonify({"error": error_message}), 500
            
    except Exception as e:
        print(f"Error creating preference: {e}")
        # Add more specific details if available from the exception
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_detail = e.response.text # Or e.response.json()
             except:
                 pass # Keep original exception string if response parsing fails
        print(f"Detailed Error: {error_detail}")
        return jsonify({"error": f"Failed to create payment preference: {error_detail}"}), 500

@app.route('/payment_feedback')
def payment_feedback():
    # Handle the user returning from Mercado Pago
    # You get payment status info in query parameters
    status = request.args.get('status')
    payment_id = request.args.get('payment_id')
    preference_id = request.args.get('preference_id')
    
    # You can use this info to show a specific message to the user
    # or update the order status in your database
    
    feedback_message = "Payment process completed."
    if status == 'approved':
        feedback_message = f"Payment successful! Payment ID: {payment_id}"
        # Potentially clear the template session here after successful payment
        # session['template_stickers'] = [] 
    elif status == 'failure':
        feedback_message = "Payment failed. Please try again or contact support."
    elif status == 'pending':
        feedback_message = "Payment is pending. We will notify you upon confirmation."
        
    # For now, just render a simple feedback page or redirect to index with a message
    # Ideally, create a dedicated feedback template
    # return render_template('feedback.html', message=feedback_message) 
    
    # Simple redirect back to index for now
    # You might want to pass the feedback message via flash messages
    # from flask import flash
    # flash(feedback_message)
    return redirect(url_for('index')) 
    # You could also return jsonify if you handle feedback purely on the frontend

# --- End Mercado Pago Integration ---

@app.route('/library')
def library():
    # Get the Mercado Pago public key from environment variables
    mp_public_key = os.getenv('MP_PUBLIC_KEY', '')
    return render_template('library.html', mp_public_key=mp_public_key)

if __name__ == '__main__':
    # Add host='0.0.0.0' to listen on all interfaces, necessary when using SERVER_NAME with dev server
    # Ensure debug=False in production
    app.run(host='0.0.0.0', debug=True) # Explicitly set host 