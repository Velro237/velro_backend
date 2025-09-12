from rest_framework.views import exception_handler
from rest_framework import status
from .utils import standard_response
import logging
import traceback

# Get logger for this module
logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Custom exception handler to standardize error responses and prevent server crashes
    """
    try:
        # Log the exception details for debugging
        request = context.get('request')
        user = getattr(request, 'user', 'Anonymous') if request else 'Unknown'
        path = getattr(request, 'path', 'Unknown') if request else 'Unknown'
        method = getattr(request, 'method', 'Unknown') if request else 'Unknown'
        
        logger.error(
            f"Exception in {method} {path} for user {user}: {str(exc)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
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
                    error_messages.extend([str(detail) for detail in exc.detail])
                else:
                    error_messages.append(str(exc.detail))
            else:
                error_messages.append(str(exc))

            return standard_response(
                status_code=response.status_code,
                error=error_messages
            )

        # Handle unexpected errors that DRF doesn't handle
        error_messages = ["An internal server error occurred. Please try again later."]
        
        # In debug mode, show the actual error
        try:
            from django.conf import settings
            if getattr(settings, 'DEBUG', False):
                error_messages = [str(exc)]
        except:
            pass
            
        return standard_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=error_messages
        )
        
    except Exception as handler_exc:
        # If our exception handler itself fails, log it and return a basic error
        try:
            logger.critical(
                f"Exception handler failed: {str(handler_exc)}\n"
                f"Original exception: {str(exc)}\n"
                f"Handler traceback: {traceback.format_exc()}"
            )
        except:
            # If even logging fails, just print to console
            print(f"Critical: Exception handler failed: {handler_exc}")
            print(f"Original exception: {exc}")
        
        # Return a basic error response
        return standard_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error=["A critical error occurred. Please contact support."]
        ) 