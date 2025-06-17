import os
import json
from datetime import timedelta
from decimal import Decimal
from dotenv import load_dotenv
import mercadopago 

# Load environment variables
load_dotenv()

# Sticker Generation Costs
LOW_STICKER_COST = 10
MEDIUM_STICKER_COST = 25
HIGH_STICKER_COST = 100

STICKER_COSTS = {
            "low": LOW_STICKER_COST,
            "medium": MEDIUM_STICKER_COST, 
            "high": HIGH_STICKER_COST
        }

COIN_PACKAGES_CONFIG = {
    'small': {'name': 'Paquete Pequeño de Monedas', 'coins': 100, 'price': 600.00, 'currency_id': 'ARS'},
    'medium': {'name': 'Paquete Mediano de Monedas', 'coins': 300, 'price': 1800.00, 'currency_id': 'ARS'},
    'large': {'name': 'Paquete Grande de Monedas', 'coins': 500, 'price': 1999.00, 'currency_id': 'ARS'}
}

STICKER_STYLE_CONFIG = {
    'Parche de hilo': 'Diseño estilo parche de hilo bordado con textura de bordado, relieve, y aspecto artesanal.',
    'Estudio Ghibli': 'Diseño estilo Ghibli con aspecto de animación japonesa, personajes de dibujos animados, y texturas de papel.',
    'Caricatura': 'Stickers con estilo caricatura dibujada a mano. Exagera rasgos caraterisicos de la imagen.',
    'Origami': 'Diseño estilo origami con pliegues de papel visibles, aspecto geométrico y texturas de papel doblado.',
    'Pixel Art': 'Diseño estilo pixel art con resolución baja, píxeles visibles y estética retro de videojuegos de los 80.',
    'Estilo Lego': 'Diseño estilo bloques de construcción con textura plástica, formas modulares y estética tipo Lego.',
    'Metalico': 'Diseño estilo metálico con acabado brillante, reflejos metálicos, aspecto de acero o aluminio pulido.',
    'Papel': 'Diseño estilo recorte de papel con textura de papel, sombras sutiles y aspecto artesanal de papel.'
}

# Coin configuration from environment variables
INITIAL_COINS = 15
BONUS_COINS = 25

# Get discount coupon settings
DISCOUNT_COUPON = os.getenv("CUPON", "")
COUPON_LIMIT = int(os.getenv("CUPON_LIMITE", "-1"))

# Development mode placeholder sticker
placeholder_value = os.getenv('USE_PLACEHOLDER_STICKER', 'False').lower()
USE_PLACEHOLDER_STICKER = placeholder_value == 'true' or placeholder_value == '1'

# Flask app configuration
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
FLASK_SERVER_NAME = os.getenv('FLASK_SERVER_NAME', None)

ADMIN_REQUEST_PASSWORD = os.getenv('ADMIN_REQUEST_PASSWORD')

# JSON configuration
JSONIFY_PRETTYPRINT_REGULAR = False

# Session configuration
SESSION_PERMANENT_LIFETIME = timedelta(days=30)
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_USE_SIGNER = True
SESSION_REFRESH_EACH_REQUEST = True

# Directory paths
FOLDER_PATH = "app/static/imgs"
TEMPLATES_PATH = "app/static/templates"

# All required directories
REQUIRED_DIRECTORIES = [
    FOLDER_PATH,
    TEMPLATES_PATH,
    "app/static/stickers",  # Carpeta alternativa para stickers
    "app/static/img"        # Para archivos estáticos como hat.png
]

# Determine if DynamoDB should be used
USE_DYNAMODB = os.getenv('USE_DYNAMODB', 'True').lower() == 'true'

# DynamoDB table names
DYNAMODB_USER_TABLE = os.getenv('DYNAMODB_USER_TABLE', 'test-thestickerhouse-users')
DYNAMODB_TRANSACTION_TABLE = os.getenv('DYNAMODB_TRANSACTION_TABLE', 'test-thestickerhouse-transactions')
DYNAMODB_REQUEST_TABLE = os.getenv('DYNAMODB_REQUEST_TABLE', 'test-thestickerhouse-admin-requests')
DYNAMODB_COUPONES_TABLE = os.getenv('DYNAMODB_COUPONES_TABLE', 'test-thestickerhouse-coupons')
DYNAMODB_STICKERS_TABLE = os.getenv('DYNAMODB_STICKERS_TABLE', 'test-thestickerhouse-stickers')

# Mercado Pago configuration
MP_ACCESS_TOKEN = os.getenv("PROD_ACCESS_TOKEN")
MP_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY', '')

# Configure Mercado Pago SDK
if not MP_ACCESS_TOKEN:
    print("Error: PROD_ACCESS_TOKEN not found in .env file.")
    # Handle the error appropriately, maybe raise an exception or use a default test token
    # For demonstration, let's allow it to continue but it won't work without a token
sdk = mercadopago.SDK(MP_ACCESS_TOKEN) if MP_ACCESS_TOKEN else None

# S3 configuration
USE_S3 = os.getenv('USE_S3', 'True')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')
S3_STICKERS_FOLDER = os.getenv('S3_STICKERS_FOLDER', 'stickers')
S3_TEMPLATES_FOLDER = os.getenv('S3_TEMPLATES_FOLDER', 'templates')

# Custom JSON encoder for handling Decimal and other DynamoDB-specific types
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, timedelta):
            return str(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super().default(obj)

# Development or production mode
FLASK_ENV = os.environ.get('FLASK_ENV', 'development') 