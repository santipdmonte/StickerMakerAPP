import base64
import time
import os
import logging
from PIL import Image
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from s3_utils import upload_file_to_s3, upload_bytes_to_s3, S3_STICKERS_FOLDER, S3_TEMPLATES_FOLDER

# Set up logging
logger = logging.getLogger(__name__)

def save_image(result, img_path, use_s3=True):
    """
    Process image and upload exclusively to S3
    
    Args:
        result: The image generation result with b64_json data
        img_path: Path used only for filename reference, file not saved locally
        use_s3: Parameter kept for backward compatibility, ignored (always True)
        
    Returns:
        tuple: (image_base64, s3_url)
    """
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    # Process image for optimal size
    image = Image.open(BytesIO(image_bytes))
    image = image.resize((250, 250), Image.LANCZOS)
    
    # Convert to bytes for upload
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    buffered.seek(0)

    # Upload to S3
    filename = os.path.basename(img_path)
    success, result = upload_bytes_to_s3(
        buffered, 
        filename, 
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success:
        s3_url = result
        logger.info(f"Successfully uploaded image to S3: {filename}")
    else:
        error_msg = f"Failed to upload image to S3: {result}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    return image_base64, s3_url


def create_placeholder_image(img_path, use_s3=True):
    """
    Create a placeholder image and upload exclusively to S3
    
    Args:
        img_path: Path used only for filename reference, file not saved locally
        use_s3: Parameter kept for backward compatibility, ignored (always True)
        
    Returns:
        tuple: (image_base64, s3_url)
    """
    time.sleep(2)

    # Use a specific image as placeholder
    placeholder_path = 'app/static/imgs/sticker_1745521616.png'
    
    # If placeholder doesn't exist, create a simple colored square
    if not os.path.exists(placeholder_path):
        img = Image.new('RGB', (250, 250), color=(73, 109, 137))
    else:
        img = Image.open(placeholder_path)
        img = img.resize((250, 250), Image.LANCZOS)
    
    # Convert to bytes for upload and base64 for response
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_str = base64.b64encode(img_bytes).decode()
    
    # Upload to S3
    filename = os.path.basename(img_path)
    buffered.seek(0)  # Reset buffer position
    success, result = upload_bytes_to_s3(
        buffered,
        filename,
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success:
        s3_url = result
        logger.info(f"Successfully uploaded placeholder to S3: {filename}")
    else:
        error_msg = f"Failed to upload placeholder to S3: {result}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    return img_str, s3_url


def create_template_zip(sticker_files, output_path):
    """
    Creates a ZIP file containing all the sticker files for a template
    
    Args:
        sticker_files (list): List of paths to sticker files
        output_path (str): Path where the ZIP file should be saved
        
    Returns:
        bool: True if successful, False otherwise
    """
    import zipfile
    
    try:
        with zipfile.ZipFile(output_path, 'w') as zipf:
            for file_path in sticker_files:
                if os.path.exists(file_path):
                    # Add file to zip with just the filename, not the full path
                    zipf.write(file_path, os.path.basename(file_path))
        return True
    except Exception as e:
        logger.error(f"Error creating template ZIP: {e}")
        return False


def send_sticker_email(customer_data, sticker_files=None, s3_urls=None):
    """
    Envía un correo electrónico a los diseñadores con la plantilla de stickers y datos del cliente.
    
    Args:
        customer_data (dict): Diccionario con datos del cliente (nombre, email, dirección, etc.)
        sticker_files (list): Lista de rutas a los archivos de stickers (obsoleto, mantenido por compatibilidad)
        s3_urls (dict): Diccionario con URLs de S3 para cada archivo (filename -> url)
        
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    if sticker_files is None:
        sticker_files = []
    if s3_urls is None:
        s3_urls = {}
        
    try:
        # Configuración del correo
        sender_email = "info@thestickerhouse.com"
        receivers = [
            "spedemonte@thestickerhouse.com",
            "gcena@thestickerhouse.com",
            "santiagopedemonte02@gmail.com"
        ]
        
        # También enviar al cliente si proporciona correo
        client_email = customer_data.get('email')
        if client_email and client_email not in receivers:
            receivers.append(client_email)
        
        # Crear mensaje
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ", ".join(receivers)
        msg['Subject'] = "Nueva orden de stickers - The Sticker House"
        
        # Cuerpo del mensaje con enlaces a S3
        s3_links_html = ""
        
        # Si tenemos una plantilla ZIP, mostrarla primero
        if s3_urls and '__template__' in s3_urls:
            s3_links_html = f"""<h3>Plantilla completa:</h3>
            <p><a href="{s3_urls['__template__']}" target="_blank">Descargar plantilla completa</a></p>
            <hr>
            <h3>Stickers individuales:</h3><ul>"""
        elif s3_urls and len(s3_urls) > 0:
            s3_links_html = "<h3>Enlaces para descargar los stickers:</h3><ul>"
        
        # Agregar enlaces a los stickers individuales
        if s3_urls and len(s3_urls) > 0:
            for filename, url in s3_urls.items():
                if filename != '__template__':  # No duplicar la plantilla
                    s3_links_html += f'<li><a href="{url}" target="_blank">{filename}</a></li>'
            s3_links_html += "</ul>"
        
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
            {s3_links_html}
            <p>Los archivos de la plantilla de stickers están disponibles en los enlaces anteriores.</p>
            <p>Por favor, procesa esta orden lo antes posible.</p>
            <p>Saludos,<br>The Sticker House</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Configurar servidor SMTP
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not smtp_username or not smtp_password:
            logger.error("SMTP credentials not found in environment variables")
            return False
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False