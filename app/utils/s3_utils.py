import os
import boto3
from botocore.exceptions import ClientError
from io import BytesIO
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Define S3 folder paths - these will still be used as defaults,
# but the app will use the values from confi.py
S3_STICKERS_FOLDER = "stickers"
S3_TEMPLATES_FOLDER = "plantillas"

def get_s3_client():
    """
    Returns a boto3 S3 client using environment variables for credentials.
    """
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not aws_access_key or not aws_secret_key:
        raise ValueError("AWS credentials not found in environment variables")
    
    return boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )

def upload_file_to_s3(file_path, object_name=None, folder=S3_STICKERS_FOLDER, bucket_name=None):
    """
    Upload a file to an S3 bucket
    
    Args:
        file_path (str): Path to file to upload
        object_name (str, optional): S3 object name. If not specified, file_path's basename is used
        folder (str, optional): S3 folder to store the file in (defaults to "stickers")
        bucket_name (str, optional): Override the default bucket name from env variables
        
    Returns:
        tuple: (bool success, str url_or_error)
    """
    bucket = bucket_name or os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket:
        return False, "AWS S3 bucket name not specified"
    
    # If S3 object_name not specified, use file_path's basename
    if object_name is None:
        object_name = os.path.basename(file_path)
    
    # Add folder prefix if it doesn't already have one
    if folder and not object_name.startswith(f"{folder}/"):
        object_name = f"{folder}/{object_name}"
    
    # Upload the file
    s3_client = get_s3_client()
    try:
        s3_client.upload_file(file_path, bucket, object_name)
        
        # Generate URL for the file
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': object_name},
            ExpiresIn=604800  # URL expires in 7 days (in seconds)
        )
        return True, presigned_url
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}")
        return False, str(e)

def upload_bytes_to_s3(file_bytes, object_name, content_type='image/png', folder=S3_STICKERS_FOLDER, bucket_name=None):
    """
    Upload bytes (like from BytesIO) to an S3 bucket
    
    Args:
        file_bytes: BytesIO or similar object containing file data
        object_name (str): S3 object name
        content_type (str): MIME type of the file
        folder (str, optional): S3 folder to store the file in (defaults to "stickers")
        bucket_name (str, optional): Override the default bucket name from env variables
        
    Returns:
        tuple: (bool success, str url_or_error)
    """
    bucket = bucket_name or os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket:
        return False, "AWS S3 bucket name not specified"
    
    # Add folder prefix if it doesn't already have one
    if folder and not object_name.startswith(f"{folder}/"):
        object_name = f"{folder}/{object_name}"
    
    # Upload the bytes data
    s3_client = get_s3_client()
    try:
        s3_client.put_object(
            Body=file_bytes,
            Bucket=bucket,
            Key=object_name,
            ContentType=content_type
        )
        
        # Generate URL for the file
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': object_name},
            ExpiresIn=604800  # URL expires in 7 days (in seconds)
        )
        return True, presigned_url
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}")
        return False, str(e)

def delete_file_from_s3(object_name, folder=None, bucket_name=None):
    """
    Delete a file from an S3 bucket
    
    Args:
        object_name (str): S3 object name to delete
        folder (str, optional): S3 folder the file is in
        bucket_name (str, optional): Override the default bucket name from env variables
        
    Returns:
        bool: True if file was deleted, False otherwise
    """
    bucket = bucket_name or os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket:
        return False
    
    # Add folder prefix if provided and not already in the object_name
    if folder and not object_name.startswith(f"{folder}/"):
        object_name = f"{folder}/{object_name}"
    
    # Delete the file
    s3_client = get_s3_client()
    try:
        s3_client.delete_object(Bucket=bucket, Key=object_name)
        return True
    except ClientError as e:
        logger.error(f"Error deleting from S3: {e}")
        return False

def upload_template_to_s3(template_file_path, template_name=None):
    """
    Upload a template file to the templates folder in S3
    
    Args:
        template_file_path (str): Path to template file to upload
        template_name (str, optional): Name to use for the template in S3
        
    Returns:
        tuple: (bool success, str url_or_error)
    """
    if template_name is None:
        template_name = os.path.basename(template_file_path)
    
    return upload_file_to_s3(
        file_path=template_file_path,
        object_name=template_name,
        folder=S3_TEMPLATES_FOLDER
    )

def list_files_in_s3_folder(folder=S3_STICKERS_FOLDER, bucket_name=None):
    """
    List all files in a specific folder in the S3 bucket
    
    Args:
        folder (str): The folder path in S3 to list
        bucket_name (str, optional): Override the default bucket name
        
    Returns:
        list: List of file keys in the folder
    """
    bucket = bucket_name or os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket:
        return []
    
    s3_client = get_s3_client()
    try:
        # Ensure folder ends with a slash
        if not folder.endswith('/'):
            folder = f"{folder}/"
        
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=folder
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                # Skip the folder itself
                if key != folder:
                    files.append(key)
        
        return files
    except ClientError as e:
        logger.error(f"Error listing files in S3 folder: {e}")
        return []

def list_files_by_user_id(user_id, folder=S3_STICKERS_FOLDER, bucket_name=None):
    """
    List all files for a specific user_id in the S3 bucket
    
    Args:
        user_id (str): The user ID to filter files by
        folder (str): The folder path in S3 to list
        bucket_name (str, optional): Override the default bucket name
        
    Returns:
        list: List of file keys for the user
    """
    bucket = bucket_name or os.getenv('AWS_S3_BUCKET_NAME')
    if not bucket:
        return []
    
    s3_client = get_s3_client()
    try:
        # Ensure folder ends with a slash
        if not folder.endswith('/'):
            folder = f"{folder}/"
        
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=folder
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                # Skip the folder itself and filter by user_id in filename
                if key != folder:
                    filename = os.path.basename(key)
                    if filename.startswith(f"sticker_{user_id}_"):
                        files.append(key)
        
        return files
    except ClientError as e:
        logger.error(f"Error listing files by user_id in S3 folder: {e}")
        return [] 