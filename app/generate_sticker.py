import base64
import io
import os
import tempfile
import logging
from utils import save_image
from openai import OpenAI
from PIL import Image

# Configurar logging
logger = logging.getLogger(__name__)

def generate_sticker(prompt, img_path, quality='low', user_id=None, style=None):
    client = OpenAI()
    
    # Aplicar estilo específico si se selecciona uno
    style_prompt = ""
    if style:
        if style == "Parche de hilo":
            style_prompt = "Diseño estilo parche de hilo bordado con textura de bordado, relieve, y aspecto artesanal."
        elif style == "Origami":
            style_prompt = "Diseño estilo origami con pliegues de papel visibles, aspecto geométrico y texturas de papel doblado."
        elif style == "Metalico":
            style_prompt = "Diseño estilo metálico con acabado brillante, reflejos metálicos, aspecto de acero o aluminio pulido."
        elif style == "Papel":
            style_prompt = "Diseño estilo recorte de papel con textura de papel, sombras sutiles y aspecto artesanal de papel."
    
    # Format the prompt with the sticker style wrapper
    formatted_prompt = f"""
<style> 
Genera estilo sticker 
{style_prompt}
</style>
<User input>
{prompt}
</User input>
"""
    
    result = client.images.generate(
        model="gpt-image-1",
        prompt=formatted_prompt,
        quality=quality,
        output_format="png",
        size="1024x1024"
    )

    # save_image now returns a tuple (image_b64, s3_url, high_res_s3_url)
    image_data = save_image(result, img_path)
    return image_data


def generate_sticker_with_reference(prompt, img_path, img_base64, quality='low', user_id=None, style=None):
    client = OpenAI()
    
    # Aplicar estilo específico si se selecciona uno
    style_prompt = ""
    if style:
        if style == "Parche de hilo":
            style_prompt = "Diseño estilo parche de hilo bordado con textura de bordado, relieve, y aspecto artesanal."
        elif style == "Origami":
            style_prompt = "Diseño estilo origami con pliegues de papel visibles, aspecto geométrico y texturas de papel doblado."
        elif style == "Metalico":
            style_prompt = "Diseño estilo metálico con acabado brillante, reflejos metálicos, aspecto de acero o aluminio pulido."
        elif style == "Papel":
            style_prompt = "Diseño estilo recorte de papel con textura de papel, sombras sutiles y aspecto artesanal de papel."
    
    # Format the prompt with the sticker style wrapper
    formatted_prompt = f"""
<style> 
Genera estilo sticker 
{style_prompt}
</style>
<User input>
{prompt}
</User input>
"""
    
    # Log para depuración
    platform_info = f"user_id: {user_id}, quality: {quality}"
    logger.info(f"Generando sticker con referencia. Platform info: {platform_info}")
    
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
            image_data = save_image(result, img_path)
            logger.info("Imagen guardada correctamente")
            return image_data
            
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