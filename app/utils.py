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
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

def save_image(result, img_path, use_s3=True):
    """
    Process image and upload exclusively to S3 in two resolutions:
    1. Original high resolution (1024x1024)
    2. Compressed low resolution (250x250)
    
    Args:
        result: The image generation result with b64_json data
        img_path: Path used only for filename reference, file not saved locally
        use_s3: Parameter kept for backward compatibility, ignored (always True)
        
    Returns:
        tuple: (image_base64, s3_url, high_res_s3_url)
    """
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)
    
    # Get original high-resolution image
    original_image = Image.open(BytesIO(image_bytes))
    
    # Create high-resolution version filename
    filename = os.path.basename(img_path)
    filename_without_ext, ext = os.path.splitext(filename)
    high_res_filename = f"{filename_without_ext}_high{ext}"
    
    # Save high-resolution version to S3
    high_res_buffered = BytesIO()
    original_image.save(high_res_buffered, format="PNG")
    high_res_buffered.seek(0)
    
    success_high, result_high = upload_bytes_to_s3(
        high_res_buffered, 
        high_res_filename, 
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success_high:
        high_res_s3_url = result_high
        logger.info(f"Successfully uploaded high resolution image to S3: {high_res_filename}")
    else:
        error_msg = f"Failed to upload high resolution image to S3: {result_high}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Process image for lower resolution version
    compressed_image = original_image.resize((250, 250), Image.LANCZOS)
    
    # Convert to bytes for upload
    low_res_buffered = BytesIO()
    compressed_image.save(low_res_buffered, format="PNG")
    low_res_buffered.seek(0)

    # Upload compressed version to S3
    success, result = upload_bytes_to_s3(
        low_res_buffered, 
        filename, 
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success:
        s3_url = result
        logger.info(f"Successfully uploaded compressed image to S3: {filename}")
    else:
        error_msg = f"Failed to upload compressed image to S3: {result}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    return image_base64, s3_url, high_res_s3_url


def create_placeholder_image(img_path, use_s3=True):
    """
    Create a placeholder image and upload exclusively to S3 in two resolutions:
    1. Original high resolution (1024x1024)
    2. Compressed low resolution (250x250)
    
    Args:
        img_path: Path used only for filename reference, file not saved locally
        use_s3: Parameter kept for backward compatibility, ignored (always True)
        
    Returns:
        tuple: (image_base64, s3_url, high_res_s3_url)
    """
    time.sleep(2)

    # Use a specific image as placeholder
    placeholder_path = 'app/static/imgs/sticker_1745521616.png'
    
    # Create high-resolution version filename
    filename = os.path.basename(img_path)
    filename_without_ext, ext = os.path.splitext(filename)
    high_res_filename = f"{filename_without_ext}_high{ext}"
    
    # If placeholder doesn't exist, create a simple colored square for both versions
    if not os.path.exists(placeholder_path):
        # Create high resolution version (1024x1024)
        high_res_img = Image.new('RGB', (1024, 1024), color=(73, 109, 137))
        
        # Create low resolution version (250x250)
        low_res_img = Image.new('RGB', (250, 250), color=(73, 109, 137))
    else:
        # Open the placeholder image
        original_img = Image.open(placeholder_path)
        
        # Create high resolution version (keep original size or resize to 1024x1024)
        if max(original_img.width, original_img.height) > 1024:
            high_res_img = original_img.resize((1024, 1024), Image.LANCZOS)
        else:
            high_res_img = original_img.copy()
        
        # Create low resolution version (250x250)
        low_res_img = original_img.resize((250, 250), Image.LANCZOS)
    
    # Save high resolution version to S3
    high_res_buffered = BytesIO()
    high_res_img.save(high_res_buffered, format="PNG")
    high_res_buffered.seek(0)
    
    success_high, result_high = upload_bytes_to_s3(
        high_res_buffered,
        high_res_filename,
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success_high:
        high_res_s3_url = result_high
        logger.info(f"Successfully uploaded high resolution placeholder to S3: {high_res_filename}")
    else:
        error_msg = f"Failed to upload high resolution placeholder to S3: {result_high}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    # Convert low resolution to bytes for upload and base64 for response
    low_res_buffered = BytesIO()
    low_res_img.save(low_res_buffered, format="PNG")
    img_bytes = low_res_buffered.getvalue()
    img_str = base64.b64encode(img_bytes).decode()
    
    # Upload low resolution to S3
    low_res_buffered.seek(0)  # Reset buffer position
    success, result = upload_bytes_to_s3(
        low_res_buffered,
        filename,
        content_type='image/png',
        folder=S3_STICKERS_FOLDER
    )
    
    if success:
        s3_url = result
        logger.info(f"Successfully uploaded compressed placeholder to S3: {filename}")
    else:
        error_msg = f"Failed to upload compressed placeholder to S3: {result}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    return img_str, s3_url, high_res_s3_url


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
        smtp_user = os.getenv('SMTP_USER')
        if not smtp_user:
            logger.error("SMTP_USER not found in environment variables")
            return False
            
        sender_email = smtp_user
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
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not smtp_server or not smtp_user or not smtp_password:
            logger.error("SMTP credentials not found in environment variables")
            return False
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


def send_login_email(email, pin):
    """
    Send a login PIN to the user's email
    
    Args:
        email (str): Recipient email address
        pin (str): Login PIN to send
        
    Returns:
        bool: True if email was sent successfully
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    # Get email configs from environment variables
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if not smtp_server or not smtp_user or not smtp_password:
        raise ValueError("SMTP credentials not found in environment variables")
    
    # Create email
    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = email
    msg['Subject'] = "Your TheStickerHouse Login PIN"
    
    # Email body
    body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
            .container {{ width: 100%; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #f8f9fa; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .pin {{ font-size: 24px; font-weight: bold; text-align: center; margin: 30px 0; letter-spacing: 5px; }}
            .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>TheStickerHouse</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Here is your login PIN for TheStickerHouse:</p>
                <p class="pin">{pin}</p>
                <p>This PIN will expire in 10 minutes.</p>
                <p>If you did not request this PIN, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; {datetime.now().year} TheStickerHouse. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    # Send email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise