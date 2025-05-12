import base64
import os
from openai import OpenAI
from PIL import Image
from io import BytesIO
from IPython.display import Image as IPImage, display

client = OpenAI()

# Create imgs/ folder
folder_path = "imgs"
os.makedirs(folder_path, exist_ok=True)

prompt = "generate a sticker picture of a green bucket hat with a pink quill on a transparent background."
img_path = "imgs/hat.png"

def save_image(result, img_path):
    image_base64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_base64)

    image = Image.open(BytesIO(image_bytes))
    image = image.resize((250, 250), Image.LANCZOS)
    image.save(img_path, format="PNG")

def generate_sticker(prompt, img_path, style=None):
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
        quality="medium",
        output_format="png",
        size="1024x1024"
    )

    save_image(result, img_path)

generate_sticker(prompt, img_path)