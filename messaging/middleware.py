from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from urllib.parse import parse_qs
from django.db import close_old_connections
from channels.db import database_sync_to_async

User = get_user_model()

class JWTAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        close_old_connections()

        # Get the token from the query string
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        if token:
            try:
                # Verify the token and get the user
                access_token = AccessToken(token)
                print(access_token)
                user_id = access_token['user_id']
                print(user_id)
                user = await self.get_user(user_id)
                print(user)
                scope['user'] = user
            except Exception as e:
                print(e)
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @staticmethod
    async def get_user(user_id):
        try:
            return await database_sync_to_async(User.objects.get)(id=user_id)
        except User.DoesNotExist:
            return AnonymousUser()

def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner)) 