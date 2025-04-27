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
    Save image to local filesystem and optionally upload to S3
    
    Args:
        result: The image generation result with b64_json data
        img_path: Local path to save the image
        use_s3: Whether to also upload to S3
        
    Returns:
        tuple: (image_base64, s3_url or None)
    """
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    # Save locally
    image = Image.open(BytesIO(image_bytes))
    image = image.resize((250, 250), Image.LANCZOS)
    image.save(img_path, format="PNG")
    
    s3_url = None
    if use_s3:
        # Upload to S3 in the stickers folder
        filename = os.path.basename(img_path)
        success, result = upload_file_to_s3(img_path, filename, folder=S3_STICKERS_FOLDER)
        if success:
            s3_url = result
        else:
            logger.error(f"Failed to upload image to S3: {result}")
    
    return image_base64, s3_url


def create_placeholder_image(img_path, use_s3=True):
    """
    Create a placeholder image and optionally upload to S3
    
    Args:
        img_path: Local path to save the image
        use_s3: Whether to also upload to S3
        
    Returns:
        tuple: (image_base64, s3_url or None)
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
    
    # Save to the destination path
    img.save(img_path, format="PNG")
    
    # Convert to base64 for response
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    s3_url = None
    if use_s3:
        # Upload to S3 in the stickers folder
        filename = os.path.basename(img_path)
        success, result = upload_file_to_s3(img_path, filename, folder=S3_STICKERS_FOLDER)
        if success:
            s3_url = result
        else:
            logger.error(f"Failed to upload image to S3: {result}")
    
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


def send_sticker_email(customer_data, sticker_files, s3_urls=None):
    """
    Envía un correo electrónico a los diseñadores con la plantilla de stickers y datos del cliente.
    
    Args:
        customer_data (dict): Diccionario con datos del cliente (nombre, email, dirección, etc.)
        sticker_files (list): Lista de rutas a los archivos de stickers
        s3_urls (dict): Diccionario con URLs de S3 para cada archivo (filename -> url)
        
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Crear un archivo ZIP con la plantilla si hay más de un sticker
        template_zip_path = None
        template_s3_url = None
        
        if len(sticker_files) > 1:
            template_name = f"plantilla_{int(time.time())}.zip"
            template_zip_path = os.path.join("app/static/templates", template_name)
            
            # Ensure the templates directory exists
            os.makedirs(os.path.dirname(template_zip_path), exist_ok=True)
            
            # Create the ZIP file
            if create_template_zip(sticker_files, template_zip_path):
                # Upload to S3 in the templates folder
                if os.path.exists(template_zip_path):
                    success, url = upload_file_to_s3(
                        template_zip_path, 
                        template_name,
                        folder=S3_TEMPLATES_FOLDER
                    )
                    if success:
                        template_s3_url = url
        
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
        if template_s3_url:
            s3_links_html = f"""<h3>Plantilla completa:</h3>
            <p><a href="{template_s3_url}" target="_blank">Descargar plantilla completa</a></p>
            <hr>
            <h3>Stickers individuales:</h3><ul>"""
        elif s3_urls and len(s3_urls) > 0:
            s3_links_html = "<h3>Enlaces para descargar los stickers:</h3><ul>"
        
        # Agregar enlaces a los stickers individuales
        if s3_urls and len(s3_urls) > 0:
            for filename, url in s3_urls.items():
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
            <p>Los archivos de la plantilla de stickers están disponibles en los enlaces anteriores o adjuntos al correo.</p>
            <p>Por favor, procesa esta orden lo antes posible.</p>
            <p>Saludos,<br>The Sticker House</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Adjuntar archivos sólo para los diseñadores internos
        if "@thestickerhouse.com" in msg['To']:
            # If we have a template ZIP, attach it
            if template_zip_path and os.path.exists(template_zip_path):
                with open(template_zip_path, 'rb') as file:
                    part = MIMEApplication(file.read(), Name=os.path.basename(template_zip_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(template_zip_path)}"'
                    msg.attach(part)
            # Otherwise attach individual files
            elif not s3_urls:
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
            
        # Clean up the template ZIP file if it was created
        if template_zip_path and os.path.exists(template_zip_path):
            try:
                os.remove(template_zip_path)
            except:
                pass
            
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar el correo: {e}")
        return False