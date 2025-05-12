import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, send_file
import time
import json
from dotenv import load_dotenv
import tempfile
from io import BytesIO
import uuid  # Add import for uuid

# Added Mercado Pago
import mercadopago 

from generate_sticker import generate_sticker, generate_sticker_with_reference
from utils import create_placeholder_image, send_sticker_email, create_template_zip
from s3_utils import (
    upload_file_to_s3, 
    upload_bytes_to_s3, 
    get_s3_client, 
    list_files_in_s3_folder,
    list_files_by_user_id,
    S3_STICKERS_FOLDER, 
    S3_TEMPLATES_FOLDER
)

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

# Get discount coupon settings
DISCOUNT_COUPON = os.getenv("CUPON", "")
COUPON_LIMIT = int(os.getenv("CUPON_LIMITE", "-1"))

# Create static directories if they don't exist
folder_path = "app/static/imgs"
templates_path = "app/static/templates"

# Asegurar que todos los directorios existan
required_directories = [
    folder_path,
    templates_path,
    "app/static/stickers",  # Carpeta alternativa para stickers
    "app/static/img"        # Para archivos estáticos como hat.png
]

for directory in required_directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Ensured directory exists: {directory}")

# Flag to determine if S3 should be used - Forzar a True para usar exclusivamente S3
USE_S3 = True

# Verify S3 configuration
try:
    # Test S3 connection
    s3_client = get_s3_client()
    bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket_name:
        raise ValueError("AWS_S3_BUCKET_NAME is not set in environment variables")
    
    # Test bucket existence
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"Successfully connected to AWS S3 bucket: {bucket_name}")
except Exception as e:
    error_msg = f"ERROR: S3 configuration is invalid or connection failed: {e}"
    print(error_msg)
    # No usar fallback a almacenamiento local, lanzar una excepción para indicar el problema
    if os.environ.get('FLASK_ENV') == 'development':
        print("Application will continue but S3 operations will fail.")
    else:
        # En producción, no permitir que la aplicación inicie sin S3 configurado
        raise RuntimeError(error_msg)

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
        session['coins'] = 85  # Start with 85 coins for new users
    
    # Initialize coupon uses if not exists
    if 'coupon_uses' not in session:
        session['coupon_uses'] = 0
    
    # Initialize user_id if not exists in session
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    # Get the Mercado Pago public key from environment variables
    mp_public_key = os.getenv('MP_PUBLIC_KEY', '')
    
    # Pass coupon info to the template
    discount_coupon = os.getenv("CUPON", "")
    coupon_limit = int(os.getenv("CUPON_LIMITE", "-1"))
    coupon_enabled = coupon_limit != 0
    coupon_uses = session.get('coupon_uses', 0)
    coupon_available = coupon_limit == -1 or coupon_uses < coupon_limit
        
    return render_template('index.html', 
                          mp_public_key=mp_public_key,
                          coupon_enabled=coupon_enabled,
                          coupon_available=coupon_available)


@app.route('/generate', methods=['POST'])
def generate():
    # Handle both form data and JSON input for flexibility
    if request.is_json:
        data = request.json
        prompt = data.get('prompt', '')
        quality = data.get('quality', 'low')
        mode = data.get('mode', 'simple')
        reference_image_data = data.get('reference_image', None)
        style = data.get('style', None)  # Obtener el estilo seleccionado
    else:
        # Handle form data with file upload
        prompt = request.form.get('prompt', '')
        quality = request.form.get('quality', 'low')
        mode = request.form.get('mode', 'simple')
        style = request.form.get('style', None)  # Obtener el estilo seleccionado
        reference_image_data = None
        
        # Check if a reference image file was uploaded
        if 'reference_image' in request.files:
            ref_file = request.files['reference_image']
            if ref_file and ref_file.filename:
                # Convert file to base64 for processing
                ref_file_data = ref_file.read()
                import base64
                reference_image_data = f"data:image/{ref_file.content_type.split('/')[-1]};base64,{base64.b64encode(ref_file_data).decode('utf-8')}"
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    # Get user_id from session, create if doesn't exist
    user_id = session.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id
    
    # Generate a unique filename based on user_id and timestamp
    timestamp = int(time.time())
    filename = f"sticker_{user_id}_{timestamp}.png"
    img_path = os.path.join(folder_path, filename)
    
    try:
        if mode == 'reference' and reference_image_data:
            # Use reference-mode function if reference image is provided
            image_b64, s3_url, high_res_s3_url = generate_sticker_with_reference(
                prompt, img_path, reference_image_data, quality, user_id=user_id, style=style
            )
        else:
            # Use simple mode if no reference image or mode is 'simple'
            image_b64, s3_url, high_res_s3_url = generate_sticker(
                prompt, img_path, quality, user_id=user_id, style=style
            )
        
        # Store S3 URLs in session for later use
        s3_urls = session.get('s3_urls', {})
        s3_urls[filename] = s3_url
        
        # Store the high resolution version URL
        filename_without_ext, ext = os.path.splitext(filename)
        high_res_filename = f"{filename_without_ext}_high{ext}"
        s3_urls[high_res_filename] = high_res_s3_url
        
        session['s3_urls'] = s3_urls
        
        return jsonify({
            "success": True, 
            "filename": filename,
            "high_res_filename": high_res_filename, 
            "image": image_b64
        })
    except ValueError as e:
        return jsonify({"error": f"Invalid image format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate-with-reference', methods=['POST'])
def generate_with_reference():
    # For backward compatibility, redirect to the unified generate endpoint
    data = request.json
    prompt = data.get('prompt', '')
    reference_image = data.get('referenceImage', '')
    quality = data.get('quality', 'low')
    style = data.get('style', None)  # Obtener el estilo seleccionado
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    if not reference_image:
        return jsonify({"error": "No reference image provided"}), 400
    
    # Create a new request to the unified endpoint
    modified_data = {
        "prompt": prompt,
        "quality": quality,
        "mode": "reference",
        "reference_image": reference_image,
        "style": style  # Incluir el estilo en los datos modificados
    }
    
    # Pass the modified data to the unified generate endpoint
    request.json = modified_data
    return generate()

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
    # Permitir solicitud de tamaño específico de página para paginación
    page = request.args.get('page', 1, type=int)
    items_per_page = request.args.get('items_per_page', 0, type=int)  # 0 = todos los items
    
    # Get sticker files - check S3 first if enabled, fall back to local files
    sticker_files = []
    
    if USE_S3:
        try:
            # Get files from S3 stickers folder
            s3_files = list_files_in_s3_folder(S3_STICKERS_FOLDER)
            
            # Extract just the filenames without folder prefix
            for file_key in s3_files:
                filename = os.path.basename(file_key)
                if filename.endswith('.png'):
                    sticker_files.append(filename)
                    
            if sticker_files:
                # Ordenar por fecha descendente (asumiendo que el nombre del archivo contiene timestamp)
                try:
                    sticker_files.sort(key=lambda x: os.path.basename(x), reverse=True)
                except:
                    pass
                    
                total_items = len(sticker_files)
                
                # Aplicar paginación si se solicitó
                if items_per_page > 0:
                    start_idx = (page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    paginated_files = sticker_files[start_idx:end_idx]
                else:
                    paginated_files = sticker_files
                
                return jsonify({
                    "success": True,
                    "stickers": paginated_files,
                    "total_items": total_items,
                    "page": page,
                    "items_per_page": items_per_page,
                    "total_pages": (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1,
                    "source": "s3"
                })
        except Exception as e:
            print(f"Error listing S3 files: {e}")
            # Fall back to local files
    
    # If S3 failed or is disabled, check local files
    try:
        for file in os.listdir(folder_path):
            if file.endswith('.png'):
                sticker_files.append(file)
        
        if sticker_files:
            # Ordenar por fecha descendente (asumiendo que el nombre del archivo contiene timestamp)
            try:
                sticker_files.sort(key=lambda x: os.path.basename(x), reverse=True)
            except:
                pass
                
            total_items = len(sticker_files)
            
            # Aplicar paginación si se solicitó
            if items_per_page > 0:
                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                paginated_files = sticker_files[start_idx:end_idx]
            else:
                paginated_files = sticker_files
            
            return jsonify({
                "success": True,
                "stickers": paginated_files,
                "total_items": total_items,
                "page": page,
                "items_per_page": items_per_page,
                "total_pages": (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1,
                "source": "local"
            })
        else:
            return jsonify({
                "success": True,
                "stickers": [],
                "total_items": 0,
                "page": 1,
                "items_per_page": items_per_page,
                "total_pages": 0,
                "source": "local"
            })
            
    except Exception as e:
        return jsonify({
            "error": str(e),
            "success": False,
            "stickers": []
        }), 500

@app.route('/get-history', methods=['GET'])
def get_history():
    # Get the current user ID from session
    user_id = session.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id
    
    # Permitir solicitud de tamaño específico de página para paginación
    page = request.args.get('page', 1, type=int)
    items_per_page = request.args.get('items_per_page', 0, type=int)  # 0 = todos los items
    
    # Get sticker files - check S3 first if enabled, fall back to local files
    sticker_files = []
    
    if USE_S3:
        try:
            # Get files from S3 stickers folder filtered by user_id
            s3_files = list_files_by_user_id(user_id, S3_STICKERS_FOLDER)
            
            # Extract just the filenames without folder prefix
            for file_key in s3_files:
                filename = os.path.basename(file_key)
                if filename.endswith('.png'):
                    sticker_files.append(filename)
                    
            if sticker_files:
                # Ordenar por fecha descendente (asumiendo que el nombre del archivo contiene timestamp)
                try:
                    sticker_files.sort(key=lambda x: os.path.basename(x), reverse=True)
                except:
                    pass
                    
                total_items = len(sticker_files)
                
                # Aplicar paginación si se solicitó
                if items_per_page > 0:
                    start_idx = (page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    paginated_files = sticker_files[start_idx:end_idx]
                else:
                    paginated_files = sticker_files
                
                return jsonify({
                    "success": True,
                    "stickers": paginated_files,
                    "total_items": total_items,
                    "page": page,
                    "items_per_page": items_per_page,
                    "total_pages": (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1,
                    "source": "s3"
                })
        except Exception as e:
            print(f"Error listing S3 files: {e}")
            # Fall back to local files
    
    # If S3 failed or is disabled, check local files
    try:
        for file in os.listdir(folder_path):
            if file.endswith('.png') and file.startswith(f"sticker_{user_id}_"):
                sticker_files.append(file)
        
        if sticker_files:
            # Ordenar por fecha descendente (asumiendo que el nombre del archivo contiene timestamp)
            try:
                sticker_files.sort(key=lambda x: os.path.basename(x), reverse=True)
            except:
                pass
                
            total_items = len(sticker_files)
            
            # Aplicar paginación si se solicitó
            if items_per_page > 0:
                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                paginated_files = sticker_files[start_idx:end_idx]
            else:
                paginated_files = sticker_files
            
            return jsonify({
                "success": True,
                "stickers": paginated_files,
                "total_items": total_items,
                "page": page,
                "items_per_page": items_per_page,
                "total_pages": (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1,
                "source": "local"
            })
        else:
            return jsonify({
                "success": True,
                "stickers": [],
                "total_items": 0,
                "page": 1,
                "items_per_page": items_per_page,
                "total_pages": 0,
                "source": "local"
            })
            
    except Exception as e:
        return jsonify({
            "error": str(e),
            "success": False,
            "stickers": []
        }), 500

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
    coupon = data.get('coupon', '').strip()
    direct_apply = data.get('direct_apply', False)
    
    # Direct coupon application without purchase
    if direct_apply:
        if not coupon:
            return jsonify({"error": "No coupon code provided"}), 400
            
        # Validate the coupon
        if coupon != DISCOUNT_COUPON:
            return jsonify({"error": "Invalid coupon code"}), 400
            
        # Check if coupon is disabled
        if COUPON_LIMIT == 0:
            return jsonify({"error": "This coupon is no longer valid."}), 400
            
        # Check usage limit for session
        coupon_uses = session.get('coupon_uses', 0)
        
        # If there's a limit and it's reached, reject
        if COUPON_LIMIT > 0 and coupon_uses >= COUPON_LIMIT:
            return jsonify({"error": "You have reached the maximum number of uses for this coupon."}), 400
            
        # Apply coupon directly - add 500 coins to user's account
        coins_added = 500
        current_coins = session.get('coins', 0)
        session['coins'] = current_coins + coins_added
        
        # Track coupon use
        session['coupon_uses'] = coupon_uses + 1
        
        return jsonify({
            "success": True,
            "message": "Coupon applied successfully",
            "coins_added": coins_added,
            "current_coins": session.get('coins', 0)
        })
    
    # Normal purchase flow
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
    coin_amount = package_info['amount']
    price = package_info['price']
    
    # Apply coupon discount if valid
    additional_coins = 0
    if coupon and coupon == DISCOUNT_COUPON:
        # Check if coupon is disabled
        if COUPON_LIMIT == 0:
            return jsonify({"error": "This coupon is no longer valid."}), 400
            
        # Check usage limit for session
        coupon_uses = session.get('coupon_uses', 0)
        
        # If there's a limit and it's reached, reject
        if COUPON_LIMIT > 0 and coupon_uses >= COUPON_LIMIT:
            return jsonify({"error": "You have reached the maximum number of uses for this coupon."}), 400
            
        # Apply coupon - add 500 coins
        additional_coins = 500
        
        # Track coupon use
        session['coupon_uses'] = coupon_uses + 1
    
    items = [{
        "title": f"{coin_amount + additional_coins} Coins Package" + (" with Discount" if additional_coins > 0 else ""),
        "quantity": 1,
        "unit_price": price,
        "currency_id": "ARS" # Or your country's currency code
    }]
    
    total_amount = price
    
    # Basic payer info
    payer = {
        "name": name,
        "email": email
    }

    # Define back URLs dynamically using url_for
    base_url = request.url_root
    
    try:
        # Force HTTPS scheme for external URLs
        success_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package, additional_coins=additional_coins)
        failure_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package, additional_coins=0)
        pending_url = url_for('coin_payment_feedback', _external=True, _scheme='https', package=coin_package, additional_coins=0)
        
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
                "amount": coin_amount,
                "additional_coins": additional_coins,
                "coupon_applied": additional_coins > 0
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
    additional_coins = int(request.args.get('additional_coins', 0))
    
    # Define coin packages with their amounts
    coin_packages = {
        "small": 100,
        "medium": 300,
        "large": 500
    }
    
    if status == 'approved' and coin_package in coin_packages:
        # Add coins to user's account
        current_coins = session.get('coins', 0)
        package_coins = coin_packages[coin_package]
        total_coins = package_coins + additional_coins
        session['coins'] = current_coins + total_coins
        
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
    address = data.get('address', '') # Obtenemos la dirección aunque no se usaba antes

    if not all([name, email]):
         return jsonify({"error": "Missing name or email for checkout."}), 400

    # Guardar los datos del cliente en la sesión para tenerlos disponibles en la ruta de retroalimentación
    session['customer_data'] = {
        'name': name,
        'email': email,
        'address': address
    }

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
    base_url = request.url_root
    
    # --- Generate Back URLs ---
    try:
        # Force HTTPS scheme for external URLs
        # Incluir datos del cliente en las URLs de retorno
        success_url = url_for('payment_feedback', _external=True, _scheme='https', 
                             name=name, email=email, address=address)
        failure_url = url_for('payment_feedback', _external=True, _scheme='https',
                             name=name, email=email, address=address)
        pending_url = url_for('payment_feedback', _external=True, _scheme='https',
                             name=name, email=email, address=address)
        
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
        
        # Obtener los datos del cliente
        customer_data = session.get('customer_data', {})
        
        # Obtener la lista de archivos de stickers
        template_stickers = session.get('template_stickers', [])
        
        # Get S3 URLs from session
        s3_urls = session.get('s3_urls', {})
        sticker_s3_urls = {}
        
        # Preparar lista de URLs de S3 para el correo
        for sticker in template_stickers:
            if isinstance(sticker, dict):
                filename = sticker.get('filename', '')
                if filename and filename in s3_urls:
                    sticker_s3_urls[filename] = s3_urls[filename]
        
        # Create a template ZIP package if there are multiple stickers
        template_zip_path = None
        template_s3_url = None
        
        if len(sticker_s3_urls) > 1 and USE_S3:
            # En este caso, necesitamos descargar las imágenes temporalmente
            # para crear el ZIP y luego subirlo a S3
            temp_dir = tempfile.mkdtemp()
            temp_files = []
            
            try:
                # Descargar archivos temporalmente para crear el ZIP
                s3_client = get_s3_client()
                bucket = os.getenv('AWS_S3_BUCKET_NAME')
                
                for filename, url in sticker_s3_urls.items():
                    # Obtener key de S3 desde URL
                    key = f"{S3_STICKERS_FOLDER}/{filename}"
                    temp_file_path = os.path.join(temp_dir, filename)
                    
                    # Descargar archivo
                    s3_client.download_file(bucket, key, temp_file_path)
                    temp_files.append(temp_file_path)
                
                # Crear template zip
                if temp_files:
                    template_name = f"plantilla_{int(time.time())}.zip"
                    template_zip_path = os.path.join(temp_dir, template_name)
                    
                    if create_template_zip(temp_files, template_zip_path):
                        # Upload to S3
                        success, url = upload_file_to_s3(
                            template_zip_path,
                            template_name,
                            folder=S3_TEMPLATES_FOLDER
                        )
                        if success:
                            template_s3_url = url
                
            finally:
                # Limpiar archivos temporales
                for file in temp_files:
                    if os.path.exists(file):
                        os.remove(file)
                if template_zip_path and os.path.exists(template_zip_path):
                    os.remove(template_zip_path)
                os.rmdir(temp_dir)
        
        # Enviar correo electrónico al diseñador y al cliente con enlaces a los archivos
        if sticker_s3_urls:
            # If we have a template URL, add it to the s3_urls
            if template_s3_url:
                sticker_s3_urls['__template__'] = template_s3_url
                
            # Enviar solo con URLs de S3, sin archivos locales
            send_sticker_email(customer_data, [], sticker_s3_urls)
            print(f"Correo enviado con éxito para el pago {payment_id}")
        else:
            print(f"No se encontraron URLs de stickers para adjuntar al correo para el pago {payment_id}")
                
        # Limpiar la sesión después del pago exitoso
        session['template_stickers'] = []
        # Limpiar los datos del cliente y URLs de S3 de la sesión
        for key in ['customer_data', 's3_urls']:
            if key in session:
                session.pop(key)
                
    elif status == 'failure':
        feedback_message = "Payment failed. Please try again or contact support."
    elif status == 'pending':
        feedback_message = "Payment is pending. We will notify you upon confirmation."
    
    # Simple redirect back to index for now
    return redirect(url_for('index'))

# --- End Mercado Pago Integration ---

@app.route('/library')
def library():
    # Get the Mercado Pago public key from environment variables
    mp_public_key = os.getenv('MP_PUBLIC_KEY', '')
    return render_template('library.html', mp_public_key=mp_public_key)

@app.route('/img/<filename>')
def get_image(filename):
    """
    Sirve imágenes exclusivamente desde S3
    """
    print(f"[GET_IMAGE] Accessing image: {filename}")
    
    # 1. Intentar obtener URL de la sesión primero
    s3_urls = session.get('s3_urls', {})
    if filename in s3_urls:
        print(f"[GET_IMAGE] Image URL found in session cache: {filename}")
        url = s3_urls[filename]
        print(f"[GET_IMAGE] Redirecting to cached S3 URL: {url}")
        
        # En lugar de redireccionar directamente, intentar descargar y servir
        # para evitar problemas de CORS cuando se usa en un canvas
        try:
            s3_client = get_s3_client()
            bucket = os.getenv('AWS_S3_BUCKET_NAME')
            key = f"{S3_STICKERS_FOLDER}/{filename}"
            
            # Descargar el archivo a memoria
            file_obj = BytesIO()
            s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=file_obj)
            file_obj.seek(0)
            
            # Determinar el tipo de contenido
            content_type = 'image/png'
            if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
                
            # Añadir cabeceras CORS
            response = make_response(send_file(
                file_obj,
                mimetype=content_type,
                as_attachment=False,
                download_name=filename
            ))
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET'
            response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
            
            return response
        except Exception as e:
            print(f"[GET_IMAGE] Error downloading from S3, using redirect: {e}")
            # Si falla, usar redirección como fallback
            return redirect(url)
    
    # 2. Si no está en la sesión, verificar si existe en S3 y crear una URL firmada
    try:
        s3_client = get_s3_client()
        bucket = os.getenv('AWS_S3_BUCKET_NAME')
        
        if not bucket:
            error_msg = "S3 bucket name not specified in environment variables"
            print(f"[GET_IMAGE] Error: {error_msg}")
            return f"Configuration error: {error_msg}", 500
        
        # Lista de posibles rutas a probar en S3
        possible_keys = [
            f"{S3_STICKERS_FOLDER}/{filename}",  # Ruta estándar con carpeta stickers
            filename,                           # Directamente en la raíz del bucket
            f"stickers/{filename}",             # Carpeta stickers estándar (por si S3_STICKERS_FOLDER es diferente)
            f"images/{filename}",               # Otra posible carpeta
            f"imgs/{filename}"                  # Otra posible carpeta
        ]
        
        # Probar cada posible ruta
        found_key = None
        for key in possible_keys:
            print(f"[GET_IMAGE] Checking if object exists in S3: {bucket}/{key}")
            try:
                s3_client.head_object(Bucket=bucket, Key=key)
                print(f"[GET_IMAGE] ✓ Object found in S3: {bucket}/{key}")
                found_key = key
                break
            except Exception as e:
                print(f"[GET_IMAGE] ✗ Object not found at {key}: {str(e)}")
        
        # Si se encontró el archivo, intentar descargarlo y servirlo
        if found_key:
            try:
                print(f"[GET_IMAGE] Downloading and serving: {bucket}/{found_key}")
                # Descargar el archivo a memoria
                file_obj = BytesIO()
                s3_client.download_fileobj(Bucket=bucket, Key=found_key, Fileobj=file_obj)
                file_obj.seek(0)
                
                # Generar URL prefirmada para futuras peticiones
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': found_key},
                    ExpiresIn=3600  # URL válida por 1 hora
                )
                
                # Guardar URL en la sesión para futuras solicitudes
                s3_urls[filename] = presigned_url
                session['s3_urls'] = s3_urls
                
                # Determinar el tipo de contenido
                content_type = 'image/png'
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif filename.lower().endswith('.gif'):
                    content_type = 'image/gif'
                
                # Añadir cabeceras CORS
                response = make_response(send_file(
                    file_obj,
                    mimetype=content_type,
                    as_attachment=False,
                    download_name=filename
                ))
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET'
                response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
                
                return response
            except Exception as e:
                print(f"[GET_IMAGE] Error serving file directly, using redirect: {e}")
                # Si falla, usar redirección como fallback
                return redirect(presigned_url)
        else:
            print(f"[GET_IMAGE] ✗ File {filename} not found in any expected S3 location")
            return f"Image {filename} not found in S3", 404
    except Exception as e:
        error_msg = f"Error accessing S3: {str(e)}"
        print(f"[GET_IMAGE] {error_msg}")
        return error_msg, 500

@app.route('/debug-s3')
def debug_s3():
    """
    Ruta de diagnóstico para verificar la conexión a S3 y listar archivos
    """
    debug_info = {
        "s3_enabled": True,  # Siempre True
        "environment_vars": {
            "aws_access_key_present": bool(os.getenv('AWS_ACCESS_KEY_ID')),
            "aws_secret_key_present": bool(os.getenv('AWS_SECRET_ACCESS_KEY')),
            "bucket_name": os.getenv('AWS_S3_BUCKET_NAME'),
            "region": os.getenv('AWS_REGION', 'us-east-1')
        },
        "stickers_folder": S3_STICKERS_FOLDER,
        "files": [],
        "errors": []
    }
    
    try:
        # Intentar conectar a S3
        s3_client = get_s3_client()
        debug_info["connection"] = "Success"
        
        # Verificar si el bucket existe
        bucket = os.getenv('AWS_S3_BUCKET_NAME')
        
        if not bucket:
            debug_info["errors"].append("AWS_S3_BUCKET_NAME not set in environment variables")
        else:
            try:
                # Verificar si el bucket existe
                s3_client.head_bucket(Bucket=bucket)
                debug_info["bucket_exists"] = True
                
                # Listar objetos en el bucket
                folder_prefix = S3_STICKERS_FOLDER + "/"
                response = s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=folder_prefix,
                    MaxKeys=10  # Limitar a 10 resultados para ser breve
                )
                
                if 'Contents' in response:
                    # Añadir detalles de los archivos encontrados
                    for obj in response['Contents']:
                        # Crear URL prefirmada para cada objeto
                        presigned_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket, 'Key': obj['Key']},
                            ExpiresIn=3600
                        )
                        
                        debug_info["files"].append({
                            "key": obj['Key'],
                            "size": obj['Size'],
                            "last_modified": str(obj['LastModified']),
                            "url": presigned_url
                        })
                else:
                    debug_info["errors"].append(f"No files found in {folder_prefix}")
                    
                # Intentar verificar la existencia de un archivo específico (uno que debería existir)
                if debug_info["files"]:
                    sample_key = debug_info["files"][0]["key"]
                    try:
                        s3_client.head_object(Bucket=bucket, Key=sample_key)
                        debug_info["sample_file_check"] = f"File {sample_key} exists"
                    except Exception as e:
                        debug_info["errors"].append(f"Error checking {sample_key}: {str(e)}")
            
            except Exception as e:
                debug_info["errors"].append(f"Error accessing bucket or listing objects: {str(e)}")
    
    except Exception as e:
        debug_info["connection"] = "Failed"
        debug_info["errors"].append(f"Connection error: {str(e)}")
    
    return jsonify(debug_info)

@app.route('/direct-s3-img/<filename>')
def direct_s3_image(filename):
    """
    Método alternativo: Descarga directamente la imagen de S3 y la sirve,
    sin usar redirección
    """
    print(f"[DIRECT-S3] Starting direct image access for: {filename}")
    
    try:
        print("[DIRECT-S3] Getting S3 client...")
        s3_client = get_s3_client()
        print("[DIRECT-S3] Got S3 client successfully")
        
        bucket = os.getenv('AWS_S3_BUCKET_NAME')
        print(f"[DIRECT-S3] Using bucket: {bucket}")
        
        if not bucket:
            error_msg = "AWS_S3_BUCKET_NAME not set in environment variables"
            print(f"[DIRECT-S3] ERROR: {error_msg}")
            return f"Configuration error: {error_msg}", 500
        
        # Lista de posibles rutas a probar
        possible_keys = [
            f"{S3_STICKERS_FOLDER}/{filename}",
            filename,
            f"stickers/{filename}",
            f"images/{filename}",
            f"imgs/{filename}"
        ]
        
        # Primero, listar todos los objetos en el bucket para diagnóstico
        try:
            print(f"[DIRECT-S3] Listing objects in bucket: {bucket} to find possible matches")
            all_objects = s3_client.list_objects_v2(Bucket=bucket)
            
            if 'Contents' in all_objects and all_objects['Contents']:
                print(f"[DIRECT-S3] ✓ Found {len(all_objects['Contents'])} objects in bucket")
                
                # Buscar posibles coincidencias para diagnóstico
                possible_matches = []
                for obj in all_objects['Contents']:
                    key = obj['Key']
                    if filename in key:
                        possible_matches.append(key)
                
                if possible_matches:
                    print(f"[DIRECT-S3] Possible matches found for {filename}:")
                    for match in possible_matches:
                        print(f"[DIRECT-S3]   - {match}")
                    
                    # Añadir las coincidencias encontradas a las rutas a probar
                    possible_keys.extend(possible_matches)
                else:
                    print(f"[DIRECT-S3] No filename matches for {filename} in bucket contents")
            else:
                print(f"[DIRECT-S3] Warning: No objects found in bucket {bucket}")
        except Exception as e:
            print(f"[DIRECT-S3] Error listing bucket contents: {str(e)}")
        
        # Intentar encontrar y descargar el archivo
        for key in possible_keys:
            try:
                print(f"[DIRECT-S3] Attempting to download: {bucket}/{key}")
                
                # Verificar si el objeto existe
                try:
                    s3_client.head_object(Bucket=bucket, Key=key)
                    print(f"[DIRECT-S3] ✓ Object exists: {bucket}/{key}")
                except Exception as e:
                    print(f"[DIRECT-S3] ✗ Object does not exist: {bucket}/{key} - {str(e)}")
                    continue
                
                # Descargar el objeto a un buffer en memoria
                file_obj = BytesIO()
                s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=file_obj)
                
                # Resetear la posición del buffer
                file_obj.seek(0)
                
                # Determinar el tipo de contenido
                content_type = 'image/png'  # Por defecto
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif filename.lower().endswith('.gif'):
                    content_type = 'image/gif'
                
                print(f"[DIRECT-S3] ✓ Success! Serving image from {bucket}/{key}")
                
                # Guardar la ruta correcta para futuras referencias
                s3_urls = session.get('s3_urls', {})
                
                # Crear URL prefirmada para esta imagen
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600
                )
                
                # Guardar la URL para futuras solicitudes
                s3_urls[filename] = presigned_url
                session['s3_urls'] = s3_urls
                
                # Crear respuesta con cabeceras CORS
                response = make_response(send_file(
                    file_obj,
                    mimetype=content_type,
                    as_attachment=False,
                    download_name=filename
                ))
                
                # Añadir cabeceras CORS y cache
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET'
                response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
                
                return response
                
            except Exception as e:
                print(f"[DIRECT-S3] Error with {key}: {str(e)}")
                continue
        
        # Si llegamos aquí, no pudimos encontrar el archivo
        print(f"[DIRECT-S3] ✗ Image {filename} not found in any location in S3 bucket")
        return f"Image {filename} not found in S3 bucket", 404
        
    except Exception as e:
        error_msg = f"Error accessing S3: {str(e)}"
        print(f"[DIRECT-S3] Error: {error_msg}")
        return error_msg, 500

@app.route('/debug-s3-bucket')
def debug_s3_bucket():
    """
    Endpoint para mostrar la estructura completa del bucket y verificar credenciales
    """
    debug_info = {
        "aws_check": {},
        "bucket_info": {},
        "folder_structure": {},
        "sample_files": [],
        "errors": []
    }
    
    # Verificar que las variables de entorno estén configuradas
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
    
    debug_info["aws_check"] = {
        "aws_access_key_present": bool(aws_access_key),
        "aws_secret_key_present": bool(aws_secret_key),
        "aws_region": aws_region,
        "bucket_name": bucket_name,
        "s3_stickers_folder": S3_STICKERS_FOLDER,
        "s3_templates_folder": S3_TEMPLATES_FOLDER
    }
    
    if not aws_access_key or not aws_secret_key:
        debug_info["errors"].append("AWS credentials missing or incomplete")
        return jsonify(debug_info)
    
    if not bucket_name:
        debug_info["errors"].append("AWS_S3_BUCKET_NAME not set")
        return jsonify(debug_info)
    
    # Verificar conexión a AWS
    try:
        # Intentar crear cliente S3
        s3_client = get_s3_client()
        debug_info["aws_check"]["connection"] = "Success"
        
        # Verificar que el bucket existe
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            debug_info["bucket_info"]["exists"] = True
        except Exception as e:
            debug_info["bucket_info"]["exists"] = False
            debug_info["bucket_info"]["error"] = str(e)
            debug_info["errors"].append(f"Bucket {bucket_name} does not exist or not accessible: {str(e)}")
            return jsonify(debug_info)
        
        # Listar objetos en el bucket (raíz)
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, Delimiter='/')
            
            if 'CommonPrefixes' in response:
                folders = [prefix['Prefix'] for prefix in response['CommonPrefixes']]
                debug_info["folder_structure"]["root_folders"] = folders
            else:
                debug_info["folder_structure"]["root_folders"] = []
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                debug_info["folder_structure"]["root_files"] = files
            else:
                debug_info["folder_structure"]["root_files"] = []
        except Exception as e:
            debug_info["errors"].append(f"Error listing bucket root: {str(e)}")
        
        # Listar objetos en la carpeta de stickers
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, 
                Prefix=f"{S3_STICKERS_FOLDER}/",
                MaxKeys=20
            )
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                debug_info["folder_structure"]["stickers_folder"] = files
                
                # Obtener algunos ejemplos
                sample_count = min(5, len(response['Contents']))
                for i in range(sample_count):
                    obj = response['Contents'][i]
                    try:
                        url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket_name, 'Key': obj['Key']},
                            ExpiresIn=3600
                        )
                        debug_info["sample_files"].append({
                            "key": obj['Key'],
                            "url": url,
                            "size": obj['Size'],
                            "last_modified": str(obj['LastModified'])
                        })
                    except Exception as e:
                        debug_info["errors"].append(f"Error generating URL for {obj['Key']}: {str(e)}")
            else:
                debug_info["folder_structure"]["stickers_folder"] = []
                debug_info["errors"].append(f"No files found in {S3_STICKERS_FOLDER}/ folder")
        except Exception as e:
            debug_info["errors"].append(f"Error listing stickers folder: {str(e)}")
        
        # Probar con 'stickers/' como alternativa si no se encontraron archivos
        if not debug_info["folder_structure"].get("stickers_folder"):
            try:
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name, 
                    Prefix="stickers/",
                    MaxKeys=5
                )
                
                if 'Contents' in response:
                    files = [obj['Key'] for obj in response['Contents']]
                    debug_info["folder_structure"]["alternate_stickers_folder"] = files
                    debug_info["notes"] = f"Found files in 'stickers/' instead of '{S3_STICKERS_FOLDER}/'"
            except Exception:
                pass
        
    except Exception as e:
        debug_info["aws_check"]["connection"] = "Failed"
        debug_info["errors"].append(f"Error connecting to AWS: {str(e)}")
    
    return jsonify(debug_info)

@app.route('/setup-dirs')
def setup_directories():
    """
    Ruta de administración para verificar y crear los directorios necesarios
    """
    result = {
        "success": True,
        "directories": {},
        "use_s3": USE_S3
    }
    
    # Lista de directorios a verificar/crear
    directories = [
        folder_path,
        templates_path,
        "app/static/stickers",
        "app/static/img",
        "app/static",
        "static/imgs",
        "imgs"
    ]
    
    for directory in directories:
        try:
            # Crear directorio si no existe
            os.makedirs(directory, exist_ok=True)
            
            # Verificar permisos
            writable = os.access(directory, os.W_OK)
            absolute_path = os.path.abspath(directory)
            exists = os.path.isdir(directory)
            
            # Listar algunos archivos en el directorio
            files = []
            if exists:
                try:
                    for f in os.listdir(directory)[:5]:  # Solo listar 5 archivos como máximo
                        if f.endswith('.png'):
                            file_path = os.path.join(directory, f)
                            files.append({
                                "name": f,
                                "size": os.path.getsize(file_path) if os.path.isfile(file_path) else 0,
                                "path": file_path
                            })
                except Exception as e:
                    files = [f"Error listing: {str(e)}"]
            
            result["directories"][directory] = {
                "exists": exists,
                "writable": writable,
                "absolute_path": absolute_path,
                "files": files
            }
        except Exception as e:
            result["directories"][directory] = {
                "error": str(e)
            }
            result["success"] = False
    
    # Crear un archivo de prueba para verificar que todo funciona
    test_file_path = os.path.join(folder_path, "test_image.png")
    try:
        # Crear una imagen simple
        from PIL import Image
        img = Image.new('RGB', (100, 100), color=(255, 0, 0))
        img.save(test_file_path)
        result["test_file"] = {
            "path": test_file_path,
            "created": True,
            "url": url_for('get_image', filename="test_image.png", _external=True)
        }
    except Exception as e:
        result["test_file"] = {
            "error": str(e),
            "created": False
        }
    
    return jsonify(result)

@app.route('/get-styles', methods=['GET'])
def get_styles():
    """
    Proporciona información sobre los estilos de stickers disponibles
    Incluye el nombre del estilo y la ruta a una imagen de ejemplo
    """
    styles = [
        {
            "id": "Parche de hilo",
            "name": "Parche de hilo",
            "description": "Stickers con apariencia de parche bordado con hilo",
            "example_image": "/static/img/styles/placeholder.png"
        },
        {
            "id": "Origami",
            "name": "Origami",
            "description": "Stickers con forma y textura de papel doblado estilo origami",
            "example_image": "/static/img/styles/placeholder.png"
        },
        {
            "id": "Metalico",
            "name": "Metálico",
            "description": "Stickers con apariencia metálica brillante",
            "example_image": "/static/img/styles/placeholder.png"
        },
        {
            "id": "Papel",
            "name": "Papel",
            "description": "Stickers con textura y aspecto de recortes de papel",
            "example_image": "/static/img/styles/placeholder.png"
        }
    ]
    
    return jsonify({
        "success": True,
        "styles": styles
    })

if __name__ == '__main__':
    # Add host='0.0.0.0' to listen on all interfaces, necessary when using SERVER_NAME with dev server
    # Ensure debug=False in production
    app.run(host='0.0.0.0', debug=True) # Explicitly set host 