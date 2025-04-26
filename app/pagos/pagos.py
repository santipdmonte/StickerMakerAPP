# SDK de Mercado Pago
import mercadopago
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Agrega credenciales
sdk = mercadopago.SDK(os.getenv("PROD_ACCESS_TOKEN"))

# Crea un ítem en la preferencia
preference_data = {
    "items": [
        {
            "title": "Plantilla de Sticker",
            "quantity": 1,
            "unit_price": 10,
        }
    ],
    "back_urls": {
        "success": "/success",
        "failure": "/failure",
        "pending": "/pendings"
    },
    "auto_return": "approved"
}

preference_response = sdk.preference().create(preference_data)
preference = preference_response["response"]

print(preference)
