import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, send_file
import time
from io import BytesIO
import uuid
from openai import BadRequestError

# Import configuration from config.py
from config import (
    INITIAL_COINS, 
    FOLDER_PATH, TEMPLATES_PATH, REQUIRED_DIRECTORIES,
    USE_S3, MP_PUBLIC_KEY,
    AWS_S3_BUCKET_NAME, S3_STICKERS_FOLDER, S3_TEMPLATES_FOLDER,
    CustomJSONEncoder, FLASK_ENV, FLASK_SECRET_KEY,
    JSONIFY_PRETTYPRINT_REGULAR, SESSION_PERMANENT_LIFETIME,
    SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE,
    SESSION_USE_SIGNER, SESSION_REFRESH_EACH_REQUEST,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
    STICKER_COSTS
)


from services.generate_sticker import generate_sticker, generate_sticker_with_reference
from utils.s3_utils import (
    get_s3_client, 
    list_files_by_user_id
)

# Import DynamoDB utils
from utils.dynamodb_utils import (
    ensure_tables_exist,
    get_user,
    create_transaction,
    verify_email_index,
)

# Import route blueprints
from routes.auth_routes import auth_bp
from routes.coin_routes import coin_bp
from routes.payment_routes import payment_bp
from routes.template_routes import template_bp
from routes.template_generation_routes import template_generation_bp
from routes.s3_routes import s3_bp
from routes.admin_routes import admin_bp
from routes.coupon_routes import coupon_bp
from routes.sticker_routes import sticker_bp

app = Flask(__name__)
# Configure Flask from configuration
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
# Set JSON encoder for Flask (compatible with older versions)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = JSONIFY_PRETTYPRINT_REGULAR
app.json_encoder = CustomJSONEncoder

# Configure session to be more persistent
app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_PERMANENT_LIFETIME
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE
app.config['SESSION_USE_SIGNER'] = SESSION_USE_SIGNER
app.config['SESSION_REFRESH_EACH_REQUEST'] = SESSION_REFRESH_EACH_REQUEST

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(coin_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(template_bp)
app.register_blueprint(template_generation_bp)
app.register_blueprint(s3_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(coupon_bp)
app.register_blueprint(sticker_bp)

# Set session to be permanent by default before any request
@app.before_request
def make_session_permanent():
    session.permanent = True

# TheStickerHouse - Sticker generation web application

# Create static directories if they don't exist
folder_path = FOLDER_PATH
templates_path = TEMPLATES_PATH

# Asegurar que todos los directorios existan
required_directories = REQUIRED_DIRECTORIES

for directory in required_directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Ensured directory exists: {directory}")

# Verify S3 configuration
try:
    # Test S3 connection
    s3_client = get_s3_client()
    bucket_name = AWS_S3_BUCKET_NAME
    if not bucket_name:
        raise ValueError("AWS_S3_BUCKET_NAME is not set in environment variables")
    
    # Test bucket existence
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"Successfully connected to AWS S3 bucket: {bucket_name}")
except Exception as e:
    error_msg = f"ERROR: S3 configuration is invalid or connection failed: {e}"
    print(error_msg)
    # No usar fallback a almacenamiento local, lanzar una excepción para indicar el problema
    if FLASK_ENV == 'development':
        print("Application will continue but S3 operations will fail.")
    else:
        # En producción, no permitir que la aplicación inicie sin S3 configurado
        raise RuntimeError(error_msg)


# Setup DB tables if enabled
try:
    ensure_tables_exist()
    verify_email_index()
    print("DB tables successfully configured")
except Exception as e:
    error_msg = f"ERROR: DB configuration is invalid or connection failed: {e}"
    print(error_msg)
    if FLASK_ENV == 'development':
        print("Application will continue but DB operations will fail.")
    else:
        # In production, don't allow the app to start without DB configured
        raise RuntimeError(error_msg)

@app.route('/')
def index():

    user_id = session.get('user_id')
    if user_id:
        # Get user from DB - this is an authenticated user
        user = get_user(user_id)
        if user:
            # Update session with latest data
            session['coins'] = user.get('coins', 0)
        else:
            # Clear invalid session
            session.pop('user_id', None)
            session.pop('email', None)
            session.pop('coins', None)
            user_id = None
    
    # Initialize session_id for anonymous visitors if not present
    if not user_id and 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    # Initialize empty template if not exists in session
    if 'template_stickers' not in session:
        session['template_stickers'] = []
    
    # Initialize coins for new sessions without authentication
    if 'coins' not in session:
        session['coins'] = INITIAL_COINS
    
    return render_template('index.html', mp_public_key=MP_PUBLIC_KEY)

@app.route('/generate', methods=['POST'])
def generate():
    if request.is_json:
        data = request.json
        prompt = data.get('prompt', '')
        quality = data.get('quality', 'low')
        mode = data.get('mode', 'simple')
        reference_image_data = data.get('reference_image', None)
        style = data.get('style', None)
    else:
        prompt = request.form.get('prompt', '')
        quality = request.form.get('quality', 'low')
        mode = request.form.get('mode', 'simple')
        style = request.form.get('style', None)
        reference_image_data = None
        if 'reference_image' in request.files:
            ref_file = request.files['reference_image']
            if ref_file and ref_file.filename:
                ref_file_data = ref_file.read()
                import base64
                reference_image_data = f"data:image/{ref_file.content_type.split('/')[-1]};base64,{base64.b64encode(ref_file_data).decode('utf-8')}"
    
    if not prompt and not (reference_image_data and style):
        return jsonify({"error": "No prompt provided. You must enter a description, or upload a reference image and select a style."}), 400
    
    user_id = session.get('user_id')
    is_logged_in = bool(user_id)
    current_coins = 0

    # Determine sticker cost based on quality
    if quality not in STICKER_COSTS:
        return jsonify({"error": f"Invalid quality: {quality}. Must be one of: {', '.join(STICKER_COSTS.keys())}"}), 400
    actual_sticker_cost = STICKER_COSTS[quality]

    try:
        if is_logged_in:
            current_user_data = get_user(user_id)
            if not current_user_data:
                session.pop('user_id', None)
                session.pop('email', None)
                return jsonify({"error": "User session invalid. Please log in again."}), 401
            current_coins = current_user_data.get('coins', 0)
        else:
            current_coins = session.get('coins', INITIAL_COINS)

        if current_coins < actual_sticker_cost:
            return jsonify({"error": f"Insufficient coins. You need {actual_sticker_cost} coins. Your balance: {current_coins}"}), 402

        # Para usuarios anónimos, utilizamos session_id en lugar de un UUID aleatorio
        if not is_logged_in:
            # Verificar que tenemos session_id para visitantes anónimos
            session_id = session.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())
                session['session_id'] = session_id
            identifier = session_id
        else:
            identifier = user_id

        timestamp = int(time.time())
        filename = f"sticker_{identifier}_{timestamp}.png"
        img_path = os.path.join(folder_path, filename)

        image_b64, s3_url, s3_url_high_res = None, None, None
        if mode == 'reference' and reference_image_data:
            image_b64, s3_url, s3_url_high_res = generate_sticker_with_reference(
                prompt, img_path, reference_image_data, quality, style=style
            )
        else:
            image_b64, s3_url, s3_url_high_res = generate_sticker(
                prompt, img_path, quality, style=style
            )
        
        if is_logged_in:
            details = {
                'prompt': prompt,
                'quality': quality,
                'mode': mode,
                'style': style or 'default',
                'filename': filename,
                'cost': actual_sticker_cost,
                'included_image': bool(reference_image_data),
                'image_url': s3_url if reference_image_data else '',
                'used_style': bool(style),
                'style_description': style if style else ''
            }
            create_transaction(
                user_id=user_id,
                coins_amount=-actual_sticker_cost,
                transaction_type='usage',
                details=details
            )
            user_after_deduction = get_user(user_id)
            if user_after_deduction:
                session['coins'] = user_after_deduction.get('coins', 0)
            else:
                app.logger.warning(f"User {user_id} not found after successful transaction. Session coins might be stale.")
        else:
            session_coins_before_deduction = session.get('coins', INITIAL_COINS)
            session['coins'] = max(0, session_coins_before_deduction - actual_sticker_cost) 
            app.logger.info(f"Anonymous user generated a sticker. Cost: {actual_sticker_cost}. New session coins: {session['coins']}")

        s3_urls = session.get('s3_urls', {})
        s3_urls[filename] = s3_url
        
        filename_without_ext, ext = os.path.splitext(filename)
        high_res_filename = f"{filename_without_ext}_high{ext}"
        s3_urls[high_res_filename] = s3_url_high_res
        
        session['s3_urls'] = s3_urls
        
        return jsonify({
            "success": True, 
            "filename": filename,
            "high_res_filename": high_res_filename, 
            "image": image_b64
        })

    except ValueError as e:
        error_str = str(e)
        if "Insufficient coins" in error_str or "Payment failed" in error_str:
            return jsonify({"error": error_str}), 402
        if "moderation_blocked" in error_str:
            return jsonify({"error": "No se pudo generar el sticker. El contenido ingresado no está permitido por nuestro sistema de seguridad. Por favor, intenta con una descripción diferente."}), 400
        if "billing_hard_limit_reached" in error_str:
            return jsonify({"error": "No se pudo generar el sticker. Ha ocurrido un problema interno. Por favor, ponte en contacto con el administrador para resolverlo."}), 400
        app.logger.error(f"ValueError during sticker generation for user {user_id or 'anonymous'}: {error_str}", exc_info=True)
        return jsonify({"error": f"Invalid image format or input: {error_str}"}), 400
    except BadRequestError as e:
        # Manejo específico para errores de OpenAI
        error_code = ''
        try:
            if hasattr(e, 'response') and hasattr(e.response, 'json'):
                error_json = e.response.json()
                error_code = error_json.get('error', {}).get('code', '')
        except Exception:
            error_code = ''
        error_str = str(e)
        if "moderation_blocked" in error_str or error_code == "moderation_blocked":
            return jsonify({"error": "No se pudo generar el sticker. El contenido ingresado no está permitido por nuestro sistema de seguridad. Por favor, intenta con una descripción diferente."}), 400
        if "billing_hard_limit_reached" in error_str or error_code == "billing_hard_limit_reached":
            return jsonify({"error": "No se pudo generar el sticker. Ha ocurrido un problema interno. Por favor, ponte en contacto con el administrador para resolverlo."}), 400
        return jsonify({"error": f"Error al generar el sticker: {error_str}"}), 400
    except Exception as e:
        app.logger.error(f"Error during sticker generation for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/get-history', methods=['GET'])
def get_history():
    # Get the current user ID from session
    user_id = session.get('user_id')
    identifier = user_id
    
    # Si no hay user_id, usamos session_id para visitantes anónimos
    if not user_id:
        session_id = session.get('session_id')
        if not session_id:
            # Crear session_id si no existe
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        identifier = session_id
    
    # Permitir solicitud de tamaño específico de página para paginación
    page = request.args.get('page', 1, type=int)
    items_per_page = request.args.get('items_per_page', 0, type=int)  # 0 = todos los items
    
    # Get sticker files - check S3 first if enabled, fall back to local files
    sticker_files = []
    
    try:
        # Get files from S3 stickers folder filtered by user_id or session_id
        s3_files = list_files_by_user_id(identifier, S3_STICKERS_FOLDER)
        
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


# --- End Mercado Pago Integration ---

@app.route('/history')
def history():
    return render_template('history.html', mp_public_key=MP_PUBLIC_KEY)


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
            "example_image": "/static/img/styles/parche_hilo_ejemplo.webp"
        },
        {
            "id": "Estudio Ghibli",
            "name": "Estudio Ghibli",
            "description": "Stickers con estética inspirada en animaciones japonesas estilo Ghibli",
            "example_image": "/static/img/styles/sticker_ghibli.png"
        },
        {
            "id": "Caricatura",
            "name": "Caricatura",
            "description": "Stickers con estilo caricatura dibujada a mano. Exagera rasgos caraterisicos de la imagen",
            "example_image": "/static/img/styles/sticker_caricatura.png"
        },
        {
            "id": "Origami",
            "name": "Origami",
            "description": "Stickers con forma y textura de papel doblado estilo origami",
            "example_image": "/static/img/styles/sticker_cohete_origami.png"
        },
        {
            "id": "Pixel Art",
            "name": "Pixel Art",
            "description": "Stickers con estilo pixelado retro de videojuegos de los 80",
            "example_image": "/static/img/styles/sticker_pixel_art.png"
        },
        {
            "id": "Estilo Lego",
            "name": "Estilo Lego",
            "description": "Stickers con apariencia de bloques de construcción tipo Lego",
            "example_image": "/static/img/styles/sticker_lego.png"
        },
        {
            "id": "Metalico",
            "name": "Metálico",
            "description": "Stickers con apariencia metálica brillante",
            "example_image": "/static/img/styles/sticker_calavera_metalico.png"
        },
        {
            "id": "Papel",
            "name": "Papel",
            "description": "Stickers con textura y aspecto de recortes de papel",
            "example_image": "/static/img/styles/sticker_perro_papel.png"
        }
    ]
    
    return jsonify({
        "success": True,
        "styles": styles
    })

@app.route('/test')
def test():
    return render_template('test.html')

if __name__ == '__main__':
    # Add host='0.0.0.0' to listen on all interfaces, necessary when using SERVER_NAME with dev server
    # Ensure debug=False in production
    app.run(host='0.0.0.0', debug=True) # Explicitly set host 