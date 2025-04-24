import os
from flask import Flask, render_template, request, jsonify, session
import time
import json

from generate_sticker import generate_sticker, generate_sticker_with_reference
from utils import create_placeholder_image


app = Flask(__name__)
app.secret_key = 'sticker_template_secret_key'  # Required for session management

# Create imgs/ folder
folder_path = "app/static/imgs"
os.makedirs(folder_path, exist_ok=True)


@app.route('/')
def index():
    # Initialize empty template if not exists in session or convert old format to new format
    if 'template_stickers' not in session:
        session['template_stickers'] = []
    else:
        # Convert any string items to object format for backward compatibility
        template_stickers = session['template_stickers']
        updated_stickers = []
        for sticker in template_stickers:
            if isinstance(sticker, str):
                updated_stickers.append({'filename': sticker, 'quantity': 1})
            else:
                updated_stickers.append(sticker)
        session['template_stickers'] = updated_stickers
        
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

@app.route('/add-to-template', methods=['POST'])
def add_to_template():
    data = request.json
    filename = data.get('filename', '')
    quantity = data.get('quantity', 1)  # Default quantity is 1
    
    if not filename:
        return jsonify({"error": "No sticker provided"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Check if sticker already exists in template
    existing_index = next((i for i, sticker in enumerate(template_stickers) 
                         if isinstance(sticker, dict) and sticker.get('filename') == filename), None)
    
    if existing_index is not None:
        # Update existing sticker quantity
        template_stickers[existing_index]['quantity'] += quantity
    else:
        # Add the new sticker to the template with quantity
        template_stickers.append({
            'filename': filename,
            'quantity': quantity
        })
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@app.route('/update-quantity', methods=['POST'])
def update_quantity():
    data = request.json
    filename = data.get('filename', '')
    quantity = data.get('quantity', 1)
    
    if not filename:
        return jsonify({"error": "No sticker specified for update"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Find the sticker and update quantity
    for sticker in template_stickers:
        if isinstance(sticker, dict) and sticker.get('filename') == filename:
            sticker['quantity'] = max(1, quantity)  # Ensure quantity is at least 1
            break
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@app.route('/get-template', methods=['GET'])
def get_template():
    template_stickers = session.get('template_stickers', [])
    return jsonify({
        "template_stickers": template_stickers
    })

@app.route('/remove-from-template', methods=['POST'])
def remove_from_template():
    data = request.json
    filename = data.get('filename', '')
    
    if not filename:
        return jsonify({"error": "No sticker specified for removal"}), 400
    
    # Get current template stickers from session
    template_stickers = session.get('template_stickers', [])
    
    # Remove the sticker if it exists in the template
    template_stickers = [s for s in template_stickers 
                        if not (isinstance(s, dict) and s.get('filename') == filename)]
    
    # Update session
    session['template_stickers'] = template_stickers
    
    return jsonify({
        "success": True, 
        "template_stickers": template_stickers
    })

@app.route('/clear-template', methods=['POST'])
def clear_template():
    # Clear the template in the session
    session['template_stickers'] = []
    
    return jsonify({
        "success": True,
        "template_stickers": []
    })

if __name__ == '__main__':
    app.run(debug=True) 