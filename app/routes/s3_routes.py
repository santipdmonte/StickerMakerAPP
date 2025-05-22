from flask import Blueprint, jsonify, session, redirect, make_response, send_file
from io import BytesIO

from s3_utils import get_s3_client
from config import AWS_S3_BUCKET_NAME, S3_STICKERS_FOLDER, S3_TEMPLATES_FOLDER, USE_S3, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION


s3_bp = Blueprint('s3', __name__)

@s3_bp.route('/img/<filename>')
def get_image(filename):
    """
    Sirve imágenes exclusivamente desde S3
    """
    print(f"[GET_IMAGE] Accessing image: {filename}")
    
    # 1. Intentar obtener URL de la sesión primero
    s3_urls = session.get('s3_urls', {})
    if filename in s3_urls:
        print(f"[GET_IMAGE] Image URL found in session cache: {filename}")
        url = s3_urls[filename]
        print(f"[GET_IMAGE] Redirecting to cached S3 URL: {url}")
        
        # En lugar de redireccionar directamente, intentar descargar y servir
        # para evitar problemas de CORS cuando se usa en un canvas
        try:
            s3_client = get_s3_client()
            bucket = AWS_S3_BUCKET_NAME
            key = f"{S3_STICKERS_FOLDER}/{filename}"
            
            # Descargar el archivo a memoria
            file_obj = BytesIO()
            s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=file_obj)
            file_obj.seek(0)
            
            # Determinar el tipo de contenido
            content_type = 'image/png'
            if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
                
            # Añadir cabeceras CORS
            response = make_response(send_file(
                file_obj,
                mimetype=content_type,
                as_attachment=False,
                download_name=filename
            ))
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET'
            response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
            
            return response
        except Exception as e:
            print(f"[GET_IMAGE] Error downloading from S3, using redirect: {e}")
            # Si falla, usar redirección como fallback
            return redirect(url)
    
    # 2. Si no está en la sesión, verificar si existe en S3 y crear una URL firmada
    try:
        s3_client = get_s3_client()
        bucket = AWS_S3_BUCKET_NAME
        
        if not bucket:
            error_msg = "S3 bucket name not specified in environment variables"
            print(f"[GET_IMAGE] Error: {error_msg}")
            return f"Configuration error: {error_msg}", 500
        
        # Lista de posibles rutas a probar en S3
        possible_keys = [
            f"{S3_STICKERS_FOLDER}/{filename}",  # Ruta estándar con carpeta stickers
            filename,                           # Directamente en la raíz del bucket
            f"stickers/{filename}",             # Carpeta stickers estándar (por si S3_STICKERS_FOLDER es diferente)
            f"images/{filename}",               # Otra posible carpeta
            f"imgs/{filename}"                  # Otra posible carpeta
        ]
        
        # Probar cada posible ruta
        found_key = None
        for key in possible_keys:
            print(f"[GET_IMAGE] Checking if object exists in S3: {bucket}/{key}")
            try:
                s3_client.head_object(Bucket=bucket, Key=key)
                print(f"[GET_IMAGE] ✓ Object found in S3: {bucket}/{key}")
                found_key = key
                break
            except Exception as e:
                print(f"[GET_IMAGE] ✗ Object not found at {key}: {str(e)}")
        
        # Si se encontró el archivo, intentar descargarlo y servirlo
        if found_key:
            try:
                print(f"[GET_IMAGE] Downloading and serving: {bucket}/{found_key}")
                # Descargar el archivo a memoria
                file_obj = BytesIO()
                s3_client.download_fileobj(Bucket=bucket, Key=found_key, Fileobj=file_obj)
                file_obj.seek(0)
                
                # Generar URL prefirmada para futuras peticiones
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': found_key},
                    ExpiresIn=3600  # URL válida por 1 hora
                )
                
                # Guardar URL en la sesión para futuras solicitudes
                s3_urls[filename] = presigned_url
                session['s3_urls'] = s3_urls
                
                # Determinar el tipo de contenido
                content_type = 'image/png'
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif filename.lower().endswith('.gif'):
                    content_type = 'image/gif'
                
                # Añadir cabeceras CORS
                response = make_response(send_file(
                    file_obj,
                    mimetype=content_type,
                    as_attachment=False,
                    download_name=filename
                ))
                
                # Añadir cabeceras CORS y cache
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET'
                response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
                
                return response
            except Exception as e:
                print(f"[GET_IMAGE] Error serving file directly, using redirect: {e}")
                # Si falla, usar redirección como fallback
                return redirect(presigned_url)
        else:
            print(f"[GET_IMAGE] ✗ File {filename} not found in any expected S3 location")
            return f"Image {filename} not found in S3", 404
    except Exception as e:
        error_msg = f"Error accessing S3: {str(e)}"
        print(f"[GET_IMAGE] {error_msg}")
        return error_msg, 500

@s3_bp.route('/debug-s3')
def debug_s3():
    """
    Ruta de diagnóstico para verificar la conexión a S3 y listar archivos
    """
    debug_info = {
        "s3_enabled": USE_S3,
        "environment_vars": {
            "aws_access_key_present": bool(AWS_ACCESS_KEY_ID),
            "aws_secret_key_present": bool(AWS_SECRET_ACCESS_KEY),
            "bucket_name": AWS_S3_BUCKET_NAME,
            "region": AWS_REGION
        },
        "stickers_folder": S3_STICKERS_FOLDER,
        "files": [],
        "errors": []
    }
    
    try:
        # Intentar conectar a S3
        s3_client = get_s3_client()
        debug_info["connection"] = "Success"
        
        # Verificar si el bucket existe
        bucket = AWS_S3_BUCKET_NAME
        
        if not bucket:
            debug_info["errors"].append("AWS_S3_BUCKET_NAME not set in environment variables")
        else:
            try:
                # Verificar si el bucket existe
                s3_client.head_bucket(Bucket=bucket)
                debug_info["bucket_exists"] = True
                
                # Listar objetos en el bucket
                folder_prefix = S3_STICKERS_FOLDER + "/"
                response = s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=folder_prefix,
                    MaxKeys=10  # Limitar a 10 resultados para ser breve
                )
                
                if 'Contents' in response:
                    # Añadir detalles de los archivos encontrados
                    for obj in response['Contents']:
                        # Crear URL prefirmada para cada objeto
                        presigned_url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket, 'Key': obj['Key']},
                            ExpiresIn=3600
                        )
                        
                        debug_info["files"].append({
                            "key": obj['Key'],
                            "size": obj['Size'],
                            "last_modified": str(obj['LastModified']),
                            "url": presigned_url
                        })
                else:
                    debug_info["errors"].append(f"No files found in {folder_prefix}")
                    
                # Intentar verificar la existencia de un archivo específico (uno que debería existir)
                if debug_info["files"]:
                    sample_key = debug_info["files"][0]["key"]
                    try:
                        s3_client.head_object(Bucket=bucket, Key=sample_key)
                        debug_info["sample_file_check"] = f"File {sample_key} exists"
                    except Exception as e:
                        debug_info["errors"].append(f"Error checking {sample_key}: {str(e)}")
            
            except Exception as e:
                debug_info["errors"].append(f"Error accessing bucket or listing objects: {str(e)}")
    
    except Exception as e:
        debug_info["connection"] = "Failed"
        debug_info["errors"].append(f"Connection error: {str(e)}")
    
    return jsonify(debug_info)

@s3_bp.route('/direct-s3-img/<filename>')
def direct_s3_image(filename):
    """
    Método alternativo: Descarga directamente la imagen de S3 y la sirve,
    sin usar redirección
    """
    print(f"[DIRECT-S3] Starting direct image access for: {filename}")
    
    try:
        print("[DIRECT-S3] Getting S3 client...")
        s3_client = get_s3_client()
        print("[DIRECT-S3] Got S3 client successfully")
        
        bucket = AWS_S3_BUCKET_NAME
        print(f"[DIRECT-S3] Using bucket: {bucket}")
        
        if not bucket:
            error_msg = "AWS_S3_BUCKET_NAME not set in environment variables"
            print(f"[DIRECT-S3] ERROR: {error_msg}")
            return f"Configuration error: {error_msg}", 500
        
        # Lista de posibles rutas a probar
        possible_keys = [
            f"{S3_STICKERS_FOLDER}/{filename}",
            filename,
            f"stickers/{filename}",
            f"images/{filename}",
            f"imgs/{filename}"
        ]
        
        # Primero, listar todos los objetos en el bucket para diagnóstico
        try:
            print(f"[DIRECT-S3] Listing objects in bucket: {bucket} to find possible matches")
            all_objects = s3_client.list_objects_v2(Bucket=bucket)
            
            if 'Contents' in all_objects and all_objects['Contents']:
                print(f"[DIRECT-S3] ✓ Found {len(all_objects['Contents'])} objects in bucket")
                
                # Buscar posibles coincidencias para diagnóstico
                possible_matches = []
                for obj in all_objects['Contents']:
                    key = obj['Key']
                    if filename in key:
                        possible_matches.append(key)
                
                if possible_matches:
                    print(f"[DIRECT-S3] Possible matches found for {filename}:")
                    for match in possible_matches:
                        print(f"[DIRECT-S3]   - {match}")
                    
                    # Añadir las coincidencias encontradas a las rutas a probar
                    possible_keys.extend(possible_matches)
                else:
                    print(f"[DIRECT-S3] No filename matches for {filename} in bucket contents")
            else:
                print(f"[DIRECT-S3] Warning: No objects found in bucket {bucket}")
        except Exception as e:
            print(f"[DIRECT-S3] Error listing bucket contents: {str(e)}")
        
        # Intentar encontrar y descargar el archivo
        for key in possible_keys:
            try:
                print(f"[DIRECT-S3] Attempting to download: {bucket}/{key}")
                
                # Verificar si el objeto existe
                try:
                    s3_client.head_object(Bucket=bucket, Key=key)
                    print(f"[DIRECT-S3] ✓ Object exists: {bucket}/{key}")
                except Exception as e:
                    print(f"[DIRECT-S3] ✗ Object does not exist: {bucket}/{key} - {str(e)}")
                    continue
                
                # Descargar el objeto a un buffer en memoria
                file_obj = BytesIO()
                s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=file_obj)
                
                # Resetear la posición del buffer
                file_obj.seek(0)
                
                # Determinar el tipo de contenido
                content_type = 'image/png'  # Por defecto
                if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif filename.lower().endswith('.gif'):
                    content_type = 'image/gif'
                
                print(f"[DIRECT-S3] ✓ Success! Serving image from {bucket}/{key}")
                
                # Guardar la ruta correcta para futuras referencias
                s3_urls = session.get('s3_urls', {})
                
                # Crear URL prefirmada para esta imagen
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600
                )
                
                # Guardar la URL para futuras solicitudes
                s3_urls[filename] = presigned_url
                session['s3_urls'] = s3_urls
                
                # Crear respuesta con cabeceras CORS
                response = make_response(send_file(
                    file_obj,
                    mimetype=content_type,
                    as_attachment=False,
                    download_name=filename
                ))
                
                # Añadir cabeceras CORS y cache
                response.headers['Access-Control-Allow-Origin'] = '*'
                response.headers['Access-Control-Allow-Methods'] = 'GET'
                response.headers['Cache-Control'] = 'public, max-age=86400'  # Cache por 24 horas
                
                return response
                
            except Exception as e:
                print(f"[DIRECT-S3] Error with {key}: {str(e)}")
                continue
        
        # Si llegamos aquí, no pudimos encontrar el archivo
        print(f"[DIRECT-S3] ✗ Image {filename} not found in any location in S3 bucket")
        return f"Image {filename} not found in S3 bucket", 404
        
    except Exception as e:
        error_msg = f"Error accessing S3: {str(e)}"
        print(f"[DIRECT-S3] Error: {error_msg}")
        return error_msg, 500

@s3_bp.route('/debug-s3-bucket')
def debug_s3_bucket():
    """
    Endpoint para mostrar la estructura completa del bucket y verificar credenciales
    """
    debug_info = {
        "aws_check": {},
        "bucket_info": {},
        "folder_structure": {},
        "sample_files": [],
        "errors": []
    }
    
    # Use AWS configuration from config.py
    aws_access_key = AWS_ACCESS_KEY_ID
    aws_secret_key = AWS_SECRET_ACCESS_KEY
    aws_region = AWS_REGION
    bucket_name = AWS_S3_BUCKET_NAME
    
    debug_info["aws_check"] = {
        "aws_access_key_present": bool(aws_access_key),
        "aws_secret_key_present": bool(aws_secret_key),
        "aws_region": aws_region,
        "bucket_name": bucket_name,
        "s3_stickers_folder": S3_STICKERS_FOLDER,
        "s3_templates_folder": S3_TEMPLATES_FOLDER
    }
    
    if not aws_access_key or not aws_secret_key:
        debug_info["errors"].append("AWS credentials missing or incomplete")
        return jsonify(debug_info)
    
    if not bucket_name:
        debug_info["errors"].append("AWS_S3_BUCKET_NAME not set")
        return jsonify(debug_info)
    
    # Verificar conexión a AWS
    try:
        # Intentar crear cliente S3
        s3_client = get_s3_client()
        debug_info["aws_check"]["connection"] = "Success"
        
        # Verificar que el bucket existe
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            debug_info["bucket_info"]["exists"] = True
        except Exception as e:
            debug_info["bucket_info"]["exists"] = False
            debug_info["bucket_info"]["error"] = str(e)
            debug_info["errors"].append(f"Bucket {bucket_name} does not exist or not accessible: {str(e)}")
            return jsonify(debug_info)
        
        # Listar objetos en el bucket (raíz)
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, Delimiter='/')
            
            if 'CommonPrefixes' in response:
                folders = [prefix['Prefix'] for prefix in response['CommonPrefixes']]
                debug_info["folder_structure"]["root_folders"] = folders
            else:
                debug_info["folder_structure"]["root_folders"] = []
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                debug_info["folder_structure"]["root_files"] = files
            else:
                debug_info["folder_structure"]["root_files"] = []
        except Exception as e:
            debug_info["errors"].append(f"Error listing bucket root: {str(e)}")
        
        # Listar objetos en la carpeta de stickers
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, 
                Prefix=f"{S3_STICKERS_FOLDER}/",
                MaxKeys=20
            )
            
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
                debug_info["folder_structure"]["stickers_folder"] = files
                
                # Obtener algunos ejemplos
                sample_count = min(5, len(response['Contents']))
                for i in range(sample_count):
                    obj = response['Contents'][i]
                    try:
                        url = s3_client.generate_presigned_url(
                            'get_object',
                            Params={'Bucket': bucket_name, 'Key': obj['Key']},
                            ExpiresIn=3600
                        )
                        debug_info["sample_files"].append({
                            "key": obj['Key'],
                            "url": url,
                            "size": obj['Size'],
                            "last_modified": str(obj['LastModified'])
                        })
                    except Exception as e:
                        debug_info["errors"].append(f"Error generating URL for {obj['Key']}: {str(e)}")
            else:
                debug_info["folder_structure"]["stickers_folder"] = []
                debug_info["errors"].append(f"No files found in {S3_STICKERS_FOLDER}/ folder")
        except Exception as e:
            debug_info["errors"].append(f"Error listing stickers folder: {str(e)}")
        
        # Probar con 'stickers/' como alternativa si no se encontraron archivos
        if not debug_info["folder_structure"].get("stickers_folder"):
            try:
                response = s3_client.list_objects_v2(
                    Bucket=bucket_name, 
                    Prefix="stickers/",
                    MaxKeys=5
                )
                
                if 'Contents' in response:
                    files = [obj['Key'] for obj in response['Contents']]
                    debug_info["folder_structure"]["alternate_stickers_folder"] = files
                    debug_info["notes"] = f"Found files in 'stickers/' instead of '{S3_STICKERS_FOLDER}/'"
            except Exception:
                pass
        
    except Exception as e:
        debug_info["aws_check"]["connection"] = "Failed"
        debug_info["errors"].append(f"Error connecting to AWS: {str(e)}")
    
    return jsonify(debug_info)