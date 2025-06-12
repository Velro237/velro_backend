from rest_framework.response import Response
from rest_framework import status

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