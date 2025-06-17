from flask import Blueprint, request, jsonify, send_file, current_app
import os
import tempfile
from datetime import datetime
import json

# Import template generation utilities
from utils.template_generation.template_maker_utils import TemplateMaker
from utils.template_generation.sticker_maker_utils import StickerMaker

template_generation_bp = Blueprint('template_generation', __name__)

@template_generation_bp.route('/upload-and-generate-template', methods=['POST'])
def upload_and_generate_template():
    """
    Uploads images and generates a sticker template in one request.
    
    Expected form data with files and configuration.
    """
    try:
        # Check if files were uploaded
        if 'files' not in request.files:
            return jsonify({"error": "No files uploaded"}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({"error": "No files selected"}), 400
        
        # Get configuration from form data
        template_type = request.form.get('template_type', 'sticker')
        
        # Create temporary directory for uploaded files
        import tempfile
        import uuid
        temp_dir = tempfile.mkdtemp()
        
        try:
            stickers_config = {}
            
            # Process each uploaded file
            for i, file in enumerate(files):
                if file and file.filename:
                    # Validate file type
                    if not file.content_type.startswith('image/'):
                        continue
                    
                    # Save file temporarily
                    filename = f"temp_sticker_{i}_{uuid.uuid4().hex}.png"
                    file_path = os.path.join(temp_dir, filename)
                    file.save(file_path)
                    
                    # Get configuration for this file from form data
                    quantity = int(request.form.get(f'quantity_{i}', 1))
                    border = request.form.get(f'border_{i}', 'false').lower() == 'true'
                    
                    stickers_config[f"sticker_{i}"] = {
                        "path": file_path,
                        "quantity": quantity,
                        "border": border
                    }
            
            if not stickers_config:
                return jsonify({"error": "No valid image files uploaded"}), 400
            
            # Create TemplateMaker instance
            template_maker = TemplateMaker(stickers=stickers_config)
            
            # Generate appropriate template based on type
            if template_type == 'sticker':
                return _generate_sticker_template_file(template_maker, None)
            elif template_type == 'silhouette':
                return _generate_silhouette_template_file(template_maker, None)
            elif template_type == 'both':
                return _generate_both_templates_file(template_maker, None)
            else:
                return jsonify({"error": "Invalid template_type. Must be 'sticker', 'silhouette', or 'both'"}), 400
        
        finally:
            # Cleanup temporary files
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
                
    except Exception as e:
        current_app.logger.error(f"Error uploading and generating template: {str(e)}")
        return jsonify({"error": f"Failed to generate template: {str(e)}"}), 500

@template_generation_bp.route('/generate-sticker-template', methods=['POST'])
def generate_sticker_template():
    """
    Generates a sticker template (PNG image) from user-provided sticker configuration.
    
    Expected JSON payload:
    {
        "stickers": {
            "sticker_id": {
                "path": "path/to/image.png",
                "quantity": 2,
                "border": true/false
            },
            ...
        },
        "base_template_path": "optional/path/to/base.png",
        "template_type": "sticker" or "silhouette" or "both"
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        stickers_config = data.get('stickers', {})
        base_template_path = data.get('base_template_path')
        template_type = data.get('template_type', 'sticker')  # Default to sticker template
        
        if not stickers_config:
            return jsonify({"error": "No stickers configuration provided"}), 400
        
        # Validate stickers configuration
        for sticker_id, config in stickers_config.items():
            if not isinstance(config, dict):
                return jsonify({"error": f"Invalid configuration for sticker {sticker_id}"}), 400
            
            required_fields = ['path', 'quantity', 'border']
            for field in required_fields:
                if field not in config:
                    return jsonify({"error": f"Missing '{field}' in sticker {sticker_id}"}), 400
            
            # Validate that image file exists
            image_path = config['path']
            if not os.path.exists(image_path):
                return jsonify({"error": f"Image file not found: {image_path}"}), 400
        
        # Create TemplateMaker instance
        template_maker = TemplateMaker(stickers=stickers_config)
        
        # Generate appropriate template based on type
        if template_type == 'sticker':
            return _generate_sticker_template_file(template_maker, base_template_path)
        elif template_type == 'silhouette':
            return _generate_silhouette_template_file(template_maker, base_template_path)
        elif template_type == 'both':
            return _generate_both_templates_file(template_maker, base_template_path)
        else:
            return jsonify({"error": "Invalid template_type. Must be 'sticker', 'silhouette', or 'both'"}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error generating template: {str(e)}")
        return jsonify({"error": f"Failed to generate template: {str(e)}"}), 500

def _generate_sticker_template_file(template_maker, base_template_path=None):
    """Generate and return a sticker template PNG file"""
    try:
        # Create temporary file for the template
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Set default base template if not provided
        if not base_template_path:
            base_template_path = "app/utils/template_generation/plantilla-imagenes.png"
        
        # Generate the sticker template
        template_maker.make_sticker_template(
            base_template_path=base_template_path,
            save_template_path=temp_path
        )
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sticker_template_{timestamp}.png"
        
        # Return the file and cleanup
        def cleanup():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='image/png'
        )
        
        # Schedule cleanup after response is sent
        @response.call_on_close
        def cleanup_file():
            cleanup()
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating sticker template: {str(e)}")
        raise

def _generate_silhouette_template_file(template_maker, base_template_path=None):
    """Generate and return a silhouette template PDF file"""
    try:
        # Create temporary file for the template
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Set default base template if not provided
        if not base_template_path:
            base_template_path = "app/utils/template_generation/plantilla-silutesa-de-corte.png"
        
        # Generate the silhouette template
        template_maker.make_silhouette_template(
            base_template_path=base_template_path,
            save_template_path=temp_path
        )
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"silhouette_template_{timestamp}.pdf"
        
        # Return the file and cleanup
        def cleanup():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
        # Schedule cleanup after response is sent
        @response.call_on_close
        def cleanup_file():
            cleanup()
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating silhouette template: {str(e)}")
        raise

def _generate_both_templates_file(template_maker, base_template_path=None):
    """Generate both templates and return them as a ZIP file"""
    try:
        import zipfile
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as sticker_temp:
            sticker_path = sticker_temp.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as silhouette_temp:
            silhouette_path = silhouette_temp.name
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as zip_temp:
            zip_path = zip_temp.name
        
        # Set default base templates if not provided
        if not base_template_path:
            sticker_base = "app/utils/template_generation/plantilla-imagenes.png"
            silhouette_base = "app/utils/template_generation/plantilla-silutesa-de-corte.png"
        else:
            sticker_base = base_template_path
            silhouette_base = base_template_path
        
        # Generate both templates
        template_maker.make_sticker_template(
            base_template_path=sticker_base,
            save_template_path=sticker_path
        )
        
        template_maker.make_silhouette_template(
            base_template_path=silhouette_base,
            save_template_path=silhouette_path
        )
        
        # Create ZIP file with both templates
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(sticker_path, f"sticker_template_{timestamp}.png")
            zip_file.write(silhouette_path, f"silhouette_template_{timestamp}.pdf")
        
        # Cleanup function
        def cleanup():
            try:
                os.unlink(sticker_path)
                os.unlink(silhouette_path)
                os.unlink(zip_path)
            except:
                pass
        
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=f"sticker_templates_{timestamp}.zip",
            mimetype='application/zip'
        )
        
        # Schedule cleanup after response is sent
        @response.call_on_close
        def cleanup_files():
            cleanup()
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating both templates: {str(e)}")
        raise

@template_generation_bp.route('/preview-template-grid', methods=['POST'])
def preview_template_grid():
    """
    Generates a preview of the template grid (PNG image) to show cell divisions.
    
    Expected JSON payload:
    {
        "base_template_path": "optional/path/to/base.png",
        "columns": 5,
        "rows": 7,
        "printing_sheet_size": [2828, 4000],
        "printing_sheet_security_margin": {
            "min_x": 230,
            "max_x": 2650,
            "min_y": 560,
            "max_y": 3800
        }
    }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        base_template_path = data.get('base_template_path')
        columns = data.get('columns', 5)
        rows = data.get('rows', 7)
        printing_sheet_size = data.get('printing_sheet_size', (2828, 4000))
        printing_sheet_security_margin = data.get('printing_sheet_security_margin', {
            'min_x': 230,
            'max_x': 2650,
            'min_y': 560,
            'max_y': 3800
        })
        
        # Set default base template if not provided
        if not base_template_path:
            base_template_path = "app/utils/template_generation/plantilla-imagenes.png"
        
        # Create TemplateMaker instance with custom parameters
        template_maker = TemplateMaker(
            stickers={},  # Empty stickers for grid preview
            printing_sheet_size=tuple(printing_sheet_size),
            columns=columns,
            rows=rows,
            printing_sheet_security_margin=printing_sheet_security_margin
        )
        
        # Create temporary file for preview
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Generate grid preview
        template_maker.preview_cells_in_template(
            base_template_path=base_template_path,
            save_template_path=temp_path
        )
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"template_grid_preview_{timestamp}.png"
        
        # Cleanup function
        def cleanup():
            try:
                os.unlink(temp_path)
            except:
                pass
        
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='image/png'
        )
        
        # Schedule cleanup after response is sent
        @response.call_on_close
        def cleanup_file():
            cleanup()
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error generating grid preview: {str(e)}")
        return jsonify({"error": f"Failed to generate grid preview: {str(e)}"}), 500

@template_generation_bp.route('/validate-sticker-config', methods=['POST'])
def validate_sticker_config():
    """
    Validates a sticker configuration without generating templates.
    
    Expected JSON payload:
    {
        "stickers": {
            "sticker_id": {
                "path": "path/to/image.png",
                "quantity": 2,
                "border": true/false
            },
            ...
        }
    }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.json
        stickers_config = data.get('stickers', {})
        
        if not stickers_config:
            return jsonify({"error": "No stickers configuration provided"}), 400
        
        validation_results = {
            "valid": True,
            "total_stickers": 0,
            "sticker_details": {},
            "errors": []
        }
        
        for sticker_id, config in stickers_config.items():
            sticker_result = {
                "valid": True,
                "quantity": 0,
                "border": False,
                "path_exists": False,
                "errors": []
            }
            
            # Validate structure
            if not isinstance(config, dict):
                sticker_result["valid"] = False
                sticker_result["errors"].append("Invalid configuration format")
            else:
                # Check required fields
                required_fields = ['path', 'quantity', 'border']
                for field in required_fields:
                    if field not in config:
                        sticker_result["valid"] = False
                        sticker_result["errors"].append(f"Missing '{field}' field")
                
                if sticker_result["valid"]:
                    # Validate field values
                    sticker_result["quantity"] = config.get('quantity', 0)
                    sticker_result["border"] = config.get('border', False)
                    
                    # Validate quantity
                    if not isinstance(sticker_result["quantity"], int) or sticker_result["quantity"] <= 0:
                        sticker_result["valid"] = False
                        sticker_result["errors"].append("Quantity must be a positive integer")
                    
                    # Validate border
                    if not isinstance(sticker_result["border"], bool):
                        sticker_result["valid"] = False
                        sticker_result["errors"].append("Border must be a boolean")
                    
                    # Validate path exists
                    image_path = config.get('path', '')
                    if os.path.exists(image_path):
                        sticker_result["path_exists"] = True
                    else:
                        sticker_result["valid"] = False
                        sticker_result["path_exists"] = False
                        sticker_result["errors"].append(f"Image file not found: {image_path}")
            
            validation_results["sticker_details"][sticker_id] = sticker_result
            
            if not sticker_result["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend([f"{sticker_id}: {error}" for error in sticker_result["errors"]])
            else:
                validation_results["total_stickers"] += sticker_result["quantity"]
        
        return jsonify(validation_results)
        
    except Exception as e:
        current_app.logger.error(f"Error validating sticker config: {str(e)}")
        return jsonify({"error": f"Failed to validate configuration: {str(e)}"}), 500 