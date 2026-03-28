from rest_framework import generics, permissions, parsers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response

from study_materials.ai_chat_service import StudyMaterialChatService
from study_materials.exceptions import AIServiceUnavailableError
from study_materials.throttles import AIChatUserThrottle
from study_materials.utils import record_material_download, record_material_view
from study_materials.validators import StudyMaterialValidator

from .models import StudyMaterial
from .serializers import (
    AIChatRequestSerializer,
    StudyMaterialMutationResponseSerializer,
    StudyMaterialUpdateSerializer,
    StudyMaterialUploadSerializer,
)


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


class StudyMaterialAIChatView(APIView):
    """Handle AI tutor chat requests routed through Django."""

    from core.auth import JWTAuthentication

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [AIChatUserThrottle]

    def post(self, request, *args, **kwargs):
        """Validate request and return AI-generated answer scoped to one material."""
        user = request.user
        role_code = getattr(getattr(user, "role", None), "code", "")
        if not user.is_active or role_code not in {"STUDENT", "FACULTY"}:
            return Response(
                {"detail": "Only active students or faculty can access the AI tutor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = StudyMaterialChatService.ask_question(
                user=user,
                material_id=serializer.validated_data["material_id"],
                message=serializer.validated_data["message"],
            )
        except AIServiceUnavailableError as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
            },
            status=status.HTTP_200_OK,
        )


class StudyMaterialUpdateDeleteView(APIView):
    """REST endpoints equivalent to update/delete GraphQL mutations."""

    from core.auth import JWTAuthentication

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def patch(self, request, material_id, *args, **kwargs):
        """Update a study material with faculty/HOD/admin authorization."""
        material = self._get_material(material_id)
        self._ensure_mutation_permission(request.user, material)

        serializer = StudyMaterialUpdateSerializer(
            material,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated_material = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Study material updated successfully",
                "material": StudyMaterialMutationResponseSerializer(updated_material).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, material_id, *args, **kwargs):
        """Delete a study material with faculty/HOD/admin authorization."""
        material = self._get_material(material_id)
        self._ensure_mutation_permission(request.user, material)
        title = material.title
        material.delete()
        return Response(
            {
                "success": True,
                "message": f"Study material '{title}' deleted successfully",
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_material(material_id):
        material = StudyMaterial.objects.filter(id=material_id).first()
        if not material:
            raise NotFound("Study material not found")
        return material

    @staticmethod
    def _ensure_mutation_permission(user, material):
        role_code = getattr(getattr(user, "role", None), "code", "")
        if role_code not in {"FACULTY", "HOD", "ADMIN"}:
            raise PermissionDenied("Only faculty, HOD, or admin can modify study materials")
        if role_code == "FACULTY" and material.faculty_id != user.id:
            raise PermissionDenied("You can only modify your own materials")


class StudyMaterialRecordDownloadView(APIView):
    """REST endpoint equivalent to recordMaterialDownload GraphQL mutation."""

    from core.auth import JWTAuthentication

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, material_id, *args, **kwargs):
        """Record a material download for an authorized student."""
        user = request.user
        if user.role.code != "STUDENT":
            raise PermissionDenied("Only students can record downloads")

        material = StudyMaterial.objects.filter(id=material_id).first()
        if not material:
            raise NotFound("Study material not found")

        has_access, error_message = StudyMaterialValidator.validate_material_access(material, user)
        if not has_access:
            raise PermissionDenied(error_message or "Access denied")

        ip_address = request.META.get("REMOTE_ADDR")
        record_material_download(material, user, ip_address)
        material.refresh_from_db()

        return Response(
            {
                "success": True,
                "message": "Download recorded successfully",
                "material": StudyMaterialMutationResponseSerializer(material).data,
            },
            status=status.HTTP_200_OK,
        )


class StudyMaterialRecordViewView(APIView):
    """REST endpoint equivalent to recordMaterialView GraphQL mutation."""

    from core.auth import JWTAuthentication

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, material_id, *args, **kwargs):
        """Record a material view for an authorized student."""
        user = request.user
        if user.role.code != "STUDENT":
            raise PermissionDenied("Only students can record views")

        material = StudyMaterial.objects.filter(id=material_id).first()
        if not material:
            raise NotFound("Study material not found")

        has_access, error_message = StudyMaterialValidator.validate_material_access(material, user)
        if not has_access:
            raise PermissionDenied(error_message or "Access denied")

        record_material_view(material, user)
        material.refresh_from_db()

        return Response(
            {
                "success": True,
                "message": "View recorded successfully",
                "material": StudyMaterialMutationResponseSerializer(material).data,
            },
            status=status.HTTP_200_OK,
        )
