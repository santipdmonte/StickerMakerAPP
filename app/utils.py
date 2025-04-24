import base64
import time
import os
from PIL import Image
from io import BytesIO


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