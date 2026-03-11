from rest_framework import generics, permissions, parsers, status
from rest_framework.response import Response
from .models import StudyMaterial
from .serializers import StudyMaterialUploadSerializer


class StudyMaterialUploadView(generics.CreateAPIView):
    """
    API view for faculty to upload study materials.
    Accepts multipart/form-data.
    """
    queryset = StudyMaterial.objects.all()
    serializer_class = StudyMaterialUploadSerializer
    from core.auth import JWTAuthentication
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def create(self, request, *args, **kwargs):
        # Additional check at the view level for role
        if not hasattr(request.user, 'role') or request.user.role.code not in ['FACULTY', 'HOD', 'ADMIN']:
            return Response(
                {"error": "Only faculty, HOD, or admin can upload study materials."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().create(request, *args, **kwargs)
