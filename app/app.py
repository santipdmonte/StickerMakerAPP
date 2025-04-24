import os
from flask import Flask, render_template, request, jsonify
import time

from generate_sticker import generate_sticker, generate_sticker_with_reference
from utils import create_placeholder_image


app = Flask(__name__)

# Create imgs/ folder
folder_path = "app/static/imgs"
os.makedirs(folder_path, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', '')
    quality = data.get('quality', 'low')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    # Generate a unique filename based on timestamp
    timestamp = int(time.time())
    filename = f"sticker_{timestamp}.png"
    img_path = os.path.join(folder_path, filename)
    
    try:
        image_b64 = generate_sticker(prompt, img_path, quality)
        # image_b64 = create_placeholder_image(img_path)
        
        return jsonify({"success": True, "filename": filename, "image": image_b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate-with-reference', methods=['POST'])
def generate_with_reference():
    data = request.json
    prompt = data.get('prompt', '')
    reference_image = data.get('referenceImage', '')
    quality = data.get('quality', 'low')
    
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    
    if not reference_image:
        return jsonify({"error": "No reference image provided"}), 400
    
    # Generate a unique filename based on timestamp
    timestamp = int(time.time())
    filename = f"sticker_{timestamp}.png"
    img_path = os.path.join(folder_path, filename)
    
    try:
        image_b64 = generate_sticker_with_reference(prompt, img_path, reference_image, quality)
        # image_b64 = create_placeholder_image(img_path)
        
        return jsonify({"success": True, "filename": filename, "image": image_b64})
    except ValueError as e:
        return jsonify({"error": f"Invalid image format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 