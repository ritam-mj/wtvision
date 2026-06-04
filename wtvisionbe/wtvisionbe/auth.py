# wtvisionbe/wtvisionbe/auth.py
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions

class GatewayAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        # Read headers injected by the API Gateway
        # Note: Django converts headers to uppercase prefixed with HTTP_
        user_id = request.META.get('HTTP_X_USER_ID')
        user_email = request.META.get('HTTP_X_USER_EMAIL')
        user_role = request.META.get('HTTP_X_USER_ROLE')

        if not user_id:
            # If request is to a route requiring authentication but headers are missing,
            # it means the request bypassed the Gateway (security breach!) or is unauthenticated.
            return None

        # Build a stateless, dynamic user object in memory (no DB hit!)
        user = User(
            id=user_id,
            email=user_email,
            username=user_email.split('@')[0], # Fallback username
        )
        
        # You can attach custom fields (like roles) dynamically
        user.role = user_role
        user.is_authenticated = True

        return (user, None)
