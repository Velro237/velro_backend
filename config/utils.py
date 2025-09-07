from rest_framework.response import Response
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url


def standard_response(data=None, status_code=200, message=None, error=None, meta=None):
    """
    Backward-compatible envelope:
    - Keeps old keys EXACTLY: status (string), error (list), data (object), status_code (int)
    - Adds new keys: success (bool), message (str), error_obj (dict), meta (dict)
    """
    # Legacy behavior: keep `error` as a LIST exactly as before
    if error is None:
        legacy_error_list = []
        error_obj = None
    elif isinstance(error, list):
        legacy_error_list = error
        error_obj = {"code": "ERROR", "message": "; ".join(map(str, error))}
    elif isinstance(error, dict):
        legacy_error_list = [error]  # keep old RN happy
        error_obj = error
    else:
        legacy_error_list = [str(error)]
        error_obj = {"code": "ERROR", "message": str(error)}

    payload = {
        # ✅ New fields (RN can start using these later)
        "success": (error_obj is None) and (status_code < 400),
        "message": message or ("OK" if status_code < 400 else "An error occurred"),
        "error_obj": error_obj,     # structured error
        "meta": meta or {},

        # ✅ Legacy fields (unchanged contract)
        "status": "SUCCESS" if status_code < 400 else "FAILED",
        "data": data if data is not None else {},
        "status_code": status_code,
        "error": legacy_error_list,  # ← keep as LIST
    }
    return Response(payload, status=status_code)


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


