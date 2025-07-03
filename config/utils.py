from rest_framework.response import Response
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

def standard_response(data=None, status_code=200, error=None):
    """
    Standardize API response format
    
    Args:
        data: Response data (dict or list)
        status_code: HTTP status code
        error: List of error messages
    
    Returns:
        Response object with standardized format
    """
    response_data = {
        "status": "SUCCESS" if status_code < 400 else "FAILED",
        "data": data if data is not None else {},
        "status_code": status_code,
        "error": error if error is not None else []
    }
    
    return Response(response_data, status=status_code) 

from django.conf import settings


CLOUDINARY_CLOUD_NAME = settings.CLOUDINARY_CLOUD_NAME
CLOUDINARY_API_KEY = settings.CLOUDINARY_API_KEY    
CLOUDINARY_API_SECRET = settings.CLOUDINARY_API_SECRET

# Configuration       
cloudinary.config( 
    cloud_name = CLOUDINARY_CLOUD_NAME, 
    api_key = CLOUDINARY_API_KEY, 
    api_secret = CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image(image_path, public_id=None):
    upload_result = cloudinary.uploader.upload(image_path, public_id=public_id)
    print(upload_result)
    return upload_result["secure_url"]

# upload multiple files at once
def upload_images(image_paths, public_ids=None):
    if public_ids is None:
        public_ids = [None] * len(image_paths)
    
    upload_results = []
    for image_path, public_id in zip(image_paths, public_ids):
        upload_result = cloudinary.uploader.upload(image_path, public_id=public_id)
        upload_results.append(upload_result["secure_url"])
    
    return upload_results

def delete_image(public_id):
    return cloudinary.uploader.destroy(public_id)

def optimized_image_url(public_id):
    optimized_url, _ = cloudinary_url(public_id, fetch_format="auto", quality="auto")
    return optimized_url

def auto_crop_url(public_id, width=500, height=500):
    crop_url, _ = cloudinary_url(public_id, width=width, height=height, crop="auto", gravity="auto")
    return crop_url


