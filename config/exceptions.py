from rest_framework.views import exception_handler
from rest_framework import status
from .utils import standard_response

def custom_exception_handler(exc, context):
    """
    Custom exception handler to standardize error responses
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        error_messages = []
        
        # Handle validation errors
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                for field, errors in exc.detail.items():
                    if isinstance(errors, list):
                        error_messages.extend([f"{field}: {error}" for error in errors])
                    else:
                        error_messages.append(f"{field}: {errors}")
            elif isinstance(exc.detail, list):
                error_messages.extend(exc.detail)
            else:
                error_messages.append(str(exc.detail))
        else:
            error_messages.append(str(exc))

        return standard_response(
            status_code=response.status_code,
            error=error_messages
        )

    # Handle unexpected errors
    error_messages = [str(exc)]
    return standard_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error=error_messages
    ) 