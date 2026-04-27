import io
from reportlab.pdfgen import canvas
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import JWTAuthentication
from profile_management.models import FacultyProfile, StudentProfile, IDCardTemplate
from profile_management.services import FacultyProfileService, ParentAuthService, StudentProfileService, IDCardService

from .etag_mixin import ETagMixin
from .serializers import (
    FacultyProfileSerializer,
    FacultyProfileUpdateSerializer,
    HODFacultyListQuerySerializer,
    HODFacultyListResponseSerializer,
    IDCardTemplateSerializer,
    ParentOtpRequestSerializer,
    ParentOtpVerifySerializer,
    StudentAdminUpdateSerializer,
    StudentProfilePhotoUpdateSerializer,
    StudentProfileSerializer,
    StudentProfileUpdateSerializer,
)


class StudentProfileDetailView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, register_number):
        profile = StudentProfileService.get_profile(register_number=register_number, user=request.user)
        if not profile:
            return Response({"detail": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudentProfileSerializer(profile).data)

    def patch(self, request, register_number):
        serializer = StudentProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = StudentProfileService.update_profile(
                register_number=register_number,
                data=serializer.validated_data,
                actor=request.user,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudentProfileSerializer(profile).data)


class StudentProfilePhotoUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, register_number):
        serializer = StudentProfilePhotoUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = StudentProfileService.update_profile_with_photo(
                register_number=register_number,
                data={
                    key: value
                    for key, value in serializer.validated_data.items()
                    if key != "profile_picture_base64"
                },
                actor=request.user,
                profile_picture=request.FILES.get("profile_picture"),
                profile_picture_base64=serializer.validated_data.get("profile_picture_base64"),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StudentProfileSerializer(profile).data)


class StudentAdminProfileUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, register_number):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code not in {"ADMIN", "HOD"}:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        serializer = StudentAdminUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = StudentProfileService.admin_update_profile(
                register_number=register_number,
                data=serializer.validated_data,
                actor=request.user,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(StudentProfileSerializer(profile).data)


class StudentListView(ETagMixin, generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudentProfileSerializer

    def get_queryset(self):
        params = self.request.query_params
        return StudentProfileService.list_profiles(
            user=self.request.user,
            school_id=params.get("school_id"),
            department_id=params.get("department_id"),
            course_id=params.get("course_id"),
            year=params.get("year"),
            academic_status=params.get("academic_status"),
        )


class StudentDashboardView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, register_number):
        try:
            payload = StudentProfileService.get_student_dashboard(register_number=register_number, user=request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class StudentCoursesView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, register_number):
        try:
            payload = StudentProfileService.my_courses(register_number=register_number, user=request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class StudentCourseOverviewView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, register_number):
        try:
            payload = StudentProfileService.course_overview(register_number=register_number, user=request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class FacultyProfileView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = FacultyProfileService.get_my_profile(request.user)
        if not profile:
            return Response({"detail": "Faculty profile not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacultyProfileSerializer(profile).data)

    def patch(self, request):
        serializer = FacultyProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data.pop("user_id", None)
        try:
            profile = FacultyProfileService.update_profile(
                data=serializer.validated_data,
                request_user=request.user,
                user_id=user_id,
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FacultyProfileSerializer(profile).data)


class FacultyDashboardView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = FacultyProfileService.get_dashboard(request.user)
        if payload is None:
            return Response({"detail": "No dashboard data available"}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class FacultyCoursesView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        semester_id = request.query_params.get("semester_id")
        payload = FacultyProfileService.faculty_courses(request.user, semester_id=semester_id)
        if payload is None:
            return Response({"detail": "No courses available"}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class FacultyStudentsView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = FacultyProfileService.faculty_students(
            request.user,
            search=request.query_params.get("search"),
            department_id=request.query_params.get("department_id"),
            page=int(request.query_params.get("page", 1)),
            page_size=int(request.query_params.get("page_size", 10)),
        )
        if payload is None:
            return Response({"detail": "No students available"}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class HODFacultyListView(ETagMixin, APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code not in {"HOD", "ADMIN"}:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        query_serializer = HODFacultyListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        validated = query_serializer.validated_data

        payload = FacultyProfileService.hod_faculty_list(
            user=request.user,
            search=validated.get("search"),
            designation=validated.get("designation"),
            is_active=validated.get("is_active"),
            school_id=validated.get("school_id"),
            department_id=validated.get("department_id"),
            page=validated.get("page", 1),
            page_size=validated.get("page_size", 10),
        )

        if payload is None:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        response_serializer = HODFacultyListResponseSerializer(payload)
        return Response(response_serializer.data)


class ParentRequestOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ParentOtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = ParentAuthService.request_otp(register_number=serializer.validated_data["register_number"])
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class ParentVerifyOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ParentOtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = ParentAuthService.verify_otp(
                register_number=serializer.validated_data["register_number"],
                otp=serializer.validated_data["otp"],
                relationship=serializer.validated_data.get("relationship"),
                phone_number=serializer.validated_data.get("phone_number"),
            )
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "user": payload["user"].id,
                "access_token": payload["access_token"],
                "refresh_token": payload["refresh_token"],
                "message": payload["message"],
            }
        )


from django.http import HttpResponse


class StudentIDCardPDFView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, register_number):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code not in {"ADMIN", "HOD"}:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        profile = StudentProfileService.get_profile(register_number=register_number, user=request.user)
        if not profile:
            return Response({"detail": "Student profile not found"}, status=status.HTTP_404_NOT_FOUND)

        orientation = request.query_params.get("orientation", "landscape")
        pdf_buffer = IDCardService.generate_student_pdf(profile, orientation=orientation)
        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="id_card_{register_number}.pdf"'
        return response


class FacultyIDCardPDFView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, faculty_id):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code not in {"ADMIN", "HOD"}:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            profile = FacultyProfile.objects.get(id=faculty_id)
        except FacultyProfile.DoesNotExist:
            return Response({"detail": "Faculty profile not found"}, status=status.HTTP_404_NOT_FOUND)

        orientation = request.query_params.get("orientation", "landscape")
        pdf_buffer = IDCardService.generate_faculty_pdf(profile, orientation=orientation)
        response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="id_card_faculty_{faculty_id}.pdf"'
        return response


class BulkIDCardPDFView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code not in {"ADMIN", "HOD"}:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get("ids", [])
        type = request.data.get("type", "students")
        orientation = request.data.get("orientation", "landscape")

        if not ids:
            return Response({"detail": "No IDs provided"}, status=status.HTTP_400_BAD_REQUEST)

        buffer = io.BytesIO()
        width, height = (IDCardService.CARD_WIDTH, IDCardService.CARD_HEIGHT) if orientation == 'landscape' else (IDCardService.CARD_HEIGHT, IDCardService.CARD_WIDTH)
        c = canvas.Canvas(buffer, pagesize=(width, height))

        if type == "students":
            profiles = StudentProfile.objects.filter(id__in=ids)
            for profile in profiles:
                IDCardService._front(c, profile, is_student=True, orientation=orientation)
                c.showPage()
                IDCardService._back_student(c, profile, orientation=orientation)
                c.showPage()
        else:
            profiles = FacultyProfile.objects.filter(id__in=ids)
            for profile in profiles:
                IDCardService._front(c, profile, is_student=False, orientation=orientation)
                c.showPage()
                IDCardService._back_faculty(c, profile, orientation=orientation)
                c.showPage()

        c.save()
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="bulk_id_cards.pdf"'
        return response


class IDCardTemplateView(APIView):
    """GET the current template; PATCH to update individual colour fields."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def _check_admin(self, request):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        return role_code == "ADMIN"

    def get(self, request):
        template = IDCardTemplate.get_or_create_default()
        return Response(IDCardTemplateSerializer(template).data)

    def patch(self, request):
        if not self._check_admin(request):
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        template = IDCardTemplate.get_or_create_default()
        serializer = IDCardTemplateSerializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class IDCardTemplateResetView(APIView):
    """POST to wipe custom colours and restore factory defaults."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role_code = getattr(getattr(request.user, "role", None), "code", None)
        if role_code != "ADMIN":
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        IDCardTemplate.objects.filter(name="default").delete()
        template = IDCardTemplate.get_or_create_default()  # re-creates with defaults
        return Response(IDCardTemplateSerializer(template).data)
