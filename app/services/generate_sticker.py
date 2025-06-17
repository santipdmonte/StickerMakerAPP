import base64
import io
import os
import tempfile
import logging
import time
from utils.utils import save_image, create_placeholder_image
from openai import OpenAI
from PIL import Image
from config import USE_PLACEHOLDER_STICKER, STICKER_STYLE_CONFIG, STICKER_COSTS
from services.sticker_services import create_user_sticker, StickerValidationError
from flask import session

# Configurar logging
logger = logging.getLogger(__name__)

def generate_sticker(user_prompt, img_path, quality='low', style=None):
    
    # Check if we should use placeholder instead of actual generation
    if USE_PLACEHOLDER_STICKER:
        logger.info("Using placeholder sticker instead of actual generation")
        image_data, s3_url, high_res_s3_url = create_placeholder_image(img_path)
        
        # Create sticker record in database
        identifier = session.get('user_id') if session.get('user_id') else session.get('session_id')
        
        if identifier:  # Only save if user is logged in
            try:
                create_user_sticker(
                    user_id=identifier,
                    image_url=s3_url,
                    image_url_high=high_res_s3_url,
                    is_public=False,
                    style=style,
                    generation_cost=0,
                    prompt=user_prompt,
                    metadata={
                        'quality': quality,
                        'generation_timestamp': int(time.time()),
                        'original_filename': os.path.basename(img_path),
                        'is_placeholder': True
                    }
                )
            except StickerValidationError as e:
                logger.error(f"Error al guardar el placeholder en la base de datos: {str(e)}")
                # Don't raise error for placeholder, just log it
        
        return image_data, s3_url, high_res_s3_url
        
    client = OpenAI()
    
    style_prompt = ""
    if style and style in STICKER_STYLE_CONFIG:
        style_prompt = STICKER_STYLE_CONFIG[style]
    
    # Format the prompt with the sticker style wrapper
    formatted_prompt = f"""
<style> 
Generar una imagen estilo sticker (con borde de seguridad de 10px de grosor para que al imprimir el sticker evitar que se corte el borde del sticker generado). 
La imagen debe tener un fondo transparente, para que al imprimir el sticker no se imprima el fondo.
{style_prompt}
</style>
<User input>
{user_prompt}
</User input>
"""
    
    result = client.images.generate(
        model="gpt-image-1",
        prompt=formatted_prompt,
        quality=quality,
        output_format="png",
        size="1024x1024"
    )

    # save_image now returns a tuple (image_b64, s3_url, s3_url_high_res_)
    image_data, s3_url, high_res_s3_url = save_image(result, img_path)

    # Create sticker record in database
    identifier = session.get('user_id') if session.get('user_id') else session.get('session_id')

    if identifier:  # Only save if user is logged in
        try:
            create_user_sticker(
                user_id=identifier,
                image_url=s3_url,
                image_url_high=high_res_s3_url,
                is_public=False,
                style=style,
                generation_cost=0,
                prompt=user_prompt,
                metadata={
                    'quality': quality,
                    'generation_timestamp': int(time.time()),
                    'original_filename': os.path.basename(img_path)
                }
            )
        except StickerValidationError as e:
            logger.error(f"Error al guardar el sticker en la base de datos: {str(e)}")
            # Don't raise error, just log it to avoid breaking the image generation

    return image_data, s3_url, high_res_s3_url


def generate_sticker_with_reference(user_prompt, img_path, img_base64, quality='low', style=None):
    # Check if we should use placeholder instead of actual generation
    if USE_PLACEHOLDER_STICKER:
        logger.info("Using placeholder sticker instead of actual generation with reference")
        image_data, s3_url, high_res_s3_url = create_placeholder_image(img_path)
        
        # Create sticker record in database
        user_id = session.get('user_id')
        
        if user_id:  # Only save if user is logged in
            try:
                create_user_sticker(
                    user_id=user_id,
                    image_url=s3_url,
                    image_url_high=high_res_s3_url,
                    is_public=False,
                    style=style,
                    generation_cost=0,
                    prompt=user_prompt,
                    metadata={
                        'quality': quality,
                        'generation_timestamp': int(time.time()),
                        'original_filename': os.path.basename(img_path),
                        'is_placeholder': True,
                        'has_reference_image': True
                    }
                )
            except StickerValidationError as e:
                logger.error(f"Error al guardar el placeholder con referencia en la base de datos: {str(e)}")
                # Don't raise error for placeholder, just log it
        
        return image_data, s3_url, high_res_s3_url
        
    client = OpenAI()
    
    style_prompt = ""
    if style and style in STICKER_STYLE_CONFIG:
        style_prompt = STICKER_STYLE_CONFIG[style]

    # Format the prompt with the sticker style wrapper
    formatted_prompt = f"""
<style> 
Generar una imagen estilo sticker (con borde de seguridad de 10px de grosor para que al imprimir el sticker evitar que se corte el borde del sticker generado). 
La imagen debe tener un fondo transparente, para que al imprimir el sticker no se imprima el fondo.
{style_prompt}
</style>
<User input>
{user_prompt}
</User input>
"""
    
    try:
        # Convert base64 to image file
        if img_base64.startswith('data:image'):
            # Remove the data URL prefix if present
            img_base64 = img_base64.split(',')[1]
        
        # Decode base64 string to bytes
        img_bytes = base64.b64decode(img_base64)
        logger.info(f"Imagen decodificada correctamente, tamaño: {len(img_bytes)} bytes")
        
        # Create a temporary directory that won't be automatically deleted
        temp_dir = tempfile.mkdtemp()
        tmp_file_path = os.path.join(temp_dir, "reference_image.png")
        
        try:
            # Convert to PNG format with error handling
            img = Image.open(io.BytesIO(img_bytes))
            
            # Registrar información de la imagen para depuración
            logger.info(f"Imagen cargada: formato={img.format}, tamaño={img.size}, modo={img.mode}")
            
            # Asegurar que la imagen esté en formato RGBA
            img = img.convert('RGBA')
            
            # Guardar imagen en formato PNG
            img.save(tmp_file_path, format="PNG")
            logger.info(f"Imagen temporal guardada en: {tmp_file_path}")
            
            # Verificar que el archivo existe y tiene tamaño correcto
            if os.path.exists(tmp_file_path):
                file_size = os.path.getsize(tmp_file_path)
                logger.info(f"Archivo temporal creado correctamente: {file_size} bytes")
            else:
                raise ValueError("El archivo temporal no se creó correctamente")
            
            # Open the file with proper MIME type recognition
            with open(tmp_file_path, 'rb') as img_file:
                logger.info("Enviando solicitud a OpenAI para edición de imagen")
                result = client.images.edit(
                    model="gpt-image-1",
                    image=img_file,
                    prompt=formatted_prompt,
                    quality=quality,
                    size="1024x1024",
                )
                logger.info("Respuesta de OpenAI recibida correctamente")
            
            # save_image now returns a tuple (image_b64, s3_url, high_res_s3_url)
            image_data, s3_url, high_res_s3_url = save_image(result, img_path)

            # Create sticker record in database
            user_id = session.get('user_id')

            if user_id:  # Only save if user is logged in
                try:
                    create_user_sticker(
                        user_id=user_id,
                        image_url=s3_url,
                        image_url_high=high_res_s3_url,
                        is_public=False,
                        style=style,
                        generation_cost=0,
                        prompt=user_prompt,
                        metadata={
                            'quality': quality,
                            'generation_timestamp': int(time.time()),
                            'original_filename': os.path.basename(img_path),
                            'has_reference_image': True
                        }
                    )
                except StickerValidationError as e:
                    logger.error(f"Error al guardar el sticker en la base de datos: {str(e)}")
                    # Don't raise error, just log it to avoid breaking the image generation

            logger.info("Imagen guardada correctamente")
            return image_data, s3_url, high_res_s3_url
            
        except Exception as e:
            logger.error(f"Error procesando imagen: {str(e)}", exc_info=True)
            raise ValueError(f"Error al procesar la imagen: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error general: {str(e)}", exc_info=True)
        raise
    finally:
        # Clean up the temporary file and directory
        try:
            if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
                os.remove(tmp_file_path)
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as cleanup_error:
            logger.error(f"Error al limpiar archivos temporales: {str(cleanup_error)}")