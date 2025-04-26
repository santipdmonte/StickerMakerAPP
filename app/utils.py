import base64
import time
import os
from PIL import Image
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


def save_image(result, img_path):
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    image = Image.open(BytesIO(image_bytes))
    image = image.resize((250, 250), Image.LANCZOS)
    image.save(img_path, format="PNG")
    return image_base64


def create_placeholder_image(img_path):
    time.sleep(2)

    # Use a specific image as placeholder
    placeholder_path = 'app/static/imgs/sticker_1745521616.png'
    
    # If placeholder doesn't exist, create a simple colored square
    if not os.path.exists(placeholder_path):
        img = Image.new('RGB', (250, 250), color=(73, 109, 137))
    else:
        img = Image.open(placeholder_path)
        img = img.resize((250, 250), Image.LANCZOS)
    
    # Save to the destination path
    img.save(img_path, format="PNG")
    
    # Convert to base64 for response
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str


def send_sticker_email(customer_data, sticker_files):
    """
    Envía un correo electrónico a los diseñadores con la plantilla de stickers y datos del cliente.
    
    Args:
        customer_data (dict): Diccionario con datos del cliente (nombre, email, dirección, etc.)
        sticker_files (list): Lista de rutas a los archivos de stickers a adjuntar
    
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Configuración del correo
        sender_email = "info@thestickerhouse.com"
        receivers = [
            "spedemonte@thestickerhouse.com",
            "gcena@thestickerhouse.com",
            "santiagopedemonte02@gmail.com"
        ]
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(receivers)
        msg['Subject'] = "Nueva orden de stickers - The Sticker House"
        
        # Cuerpo del mensaje
        body = f"""
        <html>
        <body>
            <h2>Nueva orden de stickers</h2>
            <h3>Datos del cliente:</h3>
            <ul>
                <li><strong>Nombre:</strong> {customer_data.get('name', 'No proporcionado')}</li>
                <li><strong>Email:</strong> {customer_data.get('email', 'No proporcionado')}</li>
                <li><strong>Dirección:</strong> {customer_data.get('address', 'No proporcionada')}</li>
            </ul>
            <p>Se adjuntan los archivos de la plantilla de stickers para imprimir.</p>
            <p>Por favor, procesa esta orden lo antes posible.</p>
            <p>Saludos,<br>The Sticker House</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar archivos
        for file_path in sticker_files:
            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    part = MIMEApplication(file.read(), Name=os.path.basename(file_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)
        
        # Configurar servidor SMTP
        # Nota: Estos valores deberían estar en variables de entorno
        smtp_server = os.getenv("SMTP_SERVER", "smtp.example.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", sender_email)
        smtp_password = os.getenv("SMTP_PASSWORD", "your-password")
        
        # Conectar al servidor y enviar el correo
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        return False