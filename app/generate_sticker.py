import base64
import io
import os
import tempfile
from utils import save_image
from openai import OpenAI
from PIL import Image


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
    
    # Convert base64 to image file
    if img_base64.startswith('data:image'):
        # Remove the data URL prefix if present
        img_base64 = img_base64.split(',')[1]
    
    # Decode base64 string to bytes
    img_bytes = base64.b64decode(img_base64)
    
    # Save to a temporary file with proper extension
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        # Convert to PNG format
        img = Image.open(io.BytesIO(img_bytes))
        img = img.convert('RGBA')
        img.save(tmp_file, format='PNG')
        tmp_file_path = tmp_file.name
    
    try:
        # Open the file with proper MIME type recognition
        with open(tmp_file_path, 'rb') as img_file:
            result = client.images.edit(
                model="gpt-image-1",
                image=img_file,
                prompt=formatted_prompt,
                quality=quality,
                size="1024x1024",
            )
        
        # save_image now returns a tuple (image_b64, s3_url, high_res_s3_url)
        image_data = save_image(result, img_path)
        return image_data
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)