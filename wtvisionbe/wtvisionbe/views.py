from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "status": "success",
            "message": "Welcome to the secure WTvision Control Center!",
            "system_status": "All systems operational",
            "timestamp": timezone.now().isoformat(),
            "gateway_data": {
                "injected_user_id": user.id,
                "injected_email": user.email,
                "injected_username": user.username,
                "injected_role": getattr(user, 'role', 'user')
            },
            "statistics": {
                "active_connections": 42,
                "api_gateway_status": "ONLINE (Port 80)",
                "database_engine": "PostgreSQL (credentials_db)"
            }
        })
