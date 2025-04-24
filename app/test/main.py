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

def generate_sticker(prompt, img_path):
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        quality="medium",
        output_format="png",
        size="1024x1024"
    )

    save_image(result, img_path)

generate_sticker(prompt, img_path)