import os
import json
from datetime import timedelta
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Coin configuration from environment variables
INITIAL_COINS = int(os.getenv('INITIAL_COINS', 15))
BONUS_COINS = int(os.getenv('BONUS_COINS', 25))

# Get discount coupon settings
DISCOUNT_COUPON = os.getenv("CUPON", "")
COUPON_LIMIT = int(os.getenv("CUPON_LIMITE", "-1"))

# Flask app configuration
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
FLASK_SERVER_NAME = os.getenv('FLASK_SERVER_NAME', None)

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

# Mercado Pago configuration
MP_ACCESS_TOKEN = os.getenv("PROD_ACCESS_TOKEN")
MP_PUBLIC_KEY = os.getenv('MP_PUBLIC_KEY', '')

# S3 configuration
USE_S3 = True  # Forzar a True para usar exclusivamente S3
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET_NAME = os.getenv('AWS_S3_BUCKET_NAME')
S3_STICKERS_FOLDER = "stickers"
S3_TEMPLATES_FOLDER = "templates"

# Custom JSON encoder for handling Decimal and other DynamoDB-specific types
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Development or production mode
FLASK_ENV = os.environ.get('FLASK_ENV', 'production') 