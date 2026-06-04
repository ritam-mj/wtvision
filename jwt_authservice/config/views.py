from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.contrib.auth.models import User
from .serializers import UserRegistrationSerializer

# Helper to set the refresh token cookie
def set_refresh_token_cookie(response, refresh_token):
    cookie_settings = settings.SIMPLE_JWT
    response.set_cookie(
        key=cookie_settings.get('AUTH_COOKIE', 'refresh_token'),
        value=refresh_token,
        expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
        httponly=settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/auth/token/refresh/'),
    )

class UserRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            # Standard Django create_user will hash the password securely
            user = User.objects.create_user(
                username=serializer.validated_data['username'],
                email=serializer.validated_data.get('email', ''),
                password=serializer.validated_data['password']
            )
            return Response({
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # authenticate verifies password against database PBKDF2 hash securely
        user = authenticate(username=username, password=password)

        if user is not None:
            if not user.is_active:
                return Response({"detail": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            # Add custom claims expected by API Gateway & frontend
            refresh['username'] = user.username
            refresh['email'] = user.email
            refresh['role'] = 'admin' if user.is_superuser else 'user'
            
            access_token = str(refresh.access_token)
            
            response = Response({
                "access": access_token,
                "message": "Login successful"
            }, status=status.HTTP_200_OK)
            
            # Securely set refresh token as an HTTP-only cookie
            set_refresh_token_cookie(response, str(refresh))
            return response
            
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE', 'refresh_token')
        refresh_token = request.COOKIES.get(cookie_name)

        if not refresh_token:
            return Response({"detail": "Refresh token cookie missing."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            # Validate refresh token and extract claims
            token = RefreshToken(refresh_token)
            user_id = token.payload.get('user_id')
            user = User.objects.get(id=user_id)
            
            # Generate a new access token
            new_access_token = str(token.access_token)
            
            response = Response({
                "access": new_access_token
            }, status=status.HTTP_200_OK)
            
            # Rotate refresh token if configuration is active
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # Generate new refresh token
                new_refresh = RefreshToken.for_user(user)
                new_refresh['username'] = user.username
                new_refresh['email'] = user.email
                new_refresh['role'] = 'admin' if user.is_superuser else 'user'
                
                # Set rotated refresh token in cookie
                set_refresh_token_cookie(response, str(new_refresh))
                
                # Attempt to blacklist the old token to prevent replay attacks
                try:
                    token.blacklist()
                except Exception:
                    pass # Suppress if blacklist app is not installed
            
            return response
        except (TokenError, User.DoesNotExist):
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE', 'refresh_token')
        refresh_token = request.COOKIES.get(cookie_name)
        
        response = Response({"message": "Logout successful"}, status=status.HTTP_200_OK)
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
                
        # Securely delete the HTTP-only cookie by setting expiration to past
        response.delete_cookie(
            key=cookie_name,
            path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/auth/token/refresh/'),
        )
        return response

class UserUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        new_username = request.data.get('new_username')
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if not new_username and not (old_password and new_password):
            return Response({"detail": "No update fields provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Update Username
        if new_username:
            if User.objects.filter(username=new_username).exclude(id=user.id).exists():
                return Response({"detail": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)
            user.username = new_username
            user.save()
            return Response({
                "message": "Username updated successfully",
                "username": user.username
            }, status=status.HTTP_200_OK)

        # 2. Update Password
        if old_password and new_password:
            if not user.check_password(old_password):
                return Response({"detail": "Incorrect current password."}, status=status.HTTP_400_BAD_REQUEST)
            
            user.set_password(new_password)
            user.save()
            return Response({
                "message": "Password updated successfully"
            }, status=status.HTTP_200_OK)

        return Response({"detail": "Invalid request parameters."}, status=status.HTTP_400_BAD_REQUEST)

