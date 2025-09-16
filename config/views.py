from rest_framework import viewsets
from .utils import standard_response


class StandardResponseViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that provides standardized response format
    """

    def _standardize_response(self, response):
        if hasattr(response, 'data'):
            return standard_response(
                data=response.data,
                status_code=response.status_code
            )
        return response

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return self._standardize_response(response)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return self._standardize_response(response)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self._standardize_response(response)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return self._standardize_response(response)

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return self._standardize_response(response)

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        return self._standardize_response(response)
