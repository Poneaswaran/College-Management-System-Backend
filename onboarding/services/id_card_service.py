import jwt
from io import BytesIO
from datetime import timedelta
import json

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from onboarding.constants import (
    ID_CARD_QR_TTL_SECONDS,
    ID_CARD_STATUS_PENDING,
    ID_CARD_STATUS_READY,
    ID_CARD_STATUS_REVOKED,
    ID_CARD_STATUS_ISSUED,
)
from configuration.services.config_service import ConfigService
from onboarding.models import FacultyIDCard, StudentIDCard
from onboarding.services.event_service import EventService
from onboarding.utils.id_generator import generate_card_number, generate_card_number_from_format
from onboarding.utils.qr_generator import build_qr_image_file


class IDCardService:
    @staticmethod
    def _build_qr_token(payload):
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def _build_pdf_content(entity_type, full_name, identity_code, department_name, card_number):
        pdf_layout = ConfigService.get(
            "onboarding.id_card.pdf_layout",
            default={
                "title": f"{entity_type} ID CARD",
                "fields": ["name", "department", "card_number"],
            },
        )
        title = pdf_layout.get("title", f"{entity_type} ID CARD")
        fields = pdf_layout.get("fields", ["name", "department", "card_number"])

        field_value_map = {
            "name": full_name,
            "identity": identity_code,
            "department": department_name,
            "card_number": card_number,
            "issued_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)

        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, 800, str(title))

        c.setFont("Helvetica", 12)
        y = 760
        for field in fields:
            label = str(field).replace("_", " ").title()
            value = field_value_map.get(field, "")
            c.drawString(50, y, f"{label}: {value}")
            y -= 20

        c.showPage()
        c.save()

        buffer.seek(0)
        return ContentFile(buffer.read())

    @staticmethod
    def _build_payload(entity_type, entity_id, card_id, card_status):
        now = timezone.now()
        ttl_seconds = ConfigService.get("onboarding.id_card.qr_ttl", ID_CARD_QR_TTL_SECONDS)
        exp = now + timedelta(seconds=int(ttl_seconds))

        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "card_id": card_id,
            "issued_at": now.isoformat(),
            "card_status": card_status,
            "exp": int(exp.timestamp()),
        }

        payload_config = ConfigService.get(
            "onboarding.id_card.qr_payload",
            default={"include_fields": ["entity_id", "card_id", "exp", "card_status", "entity_type", "issued_at"]},
        )
        include_fields = payload_config.get("include_fields", [])
        if include_fields:
            filtered = {}
            for field in include_fields:
                if field in payload:
                    filtered[field] = payload[field]
            return filtered
        return payload

    @staticmethod
    def _build_card_number(prefix, identity_code):
        format_pattern = ConfigService.get("onboarding.id_card.format", "PREFIX-ID-RANDOM")
        if format_pattern:
            return generate_card_number_from_format(prefix, identity_code, format_pattern)
        return generate_card_number(prefix, identity_code)

    @staticmethod
    def generate_student_id_card(student_profile, generated_by):
        if not ConfigService.get_bool("onboarding.features.enable_id_card_generation", True):
            raise ValueError("ID card generation is disabled by configuration")

        card, _ = StudentIDCard.objects.get_or_create(
            student_profile=student_profile,
            defaults={
                "card_number": IDCardService._build_card_number("STU", student_profile.register_number),
                "status": ID_CARD_STATUS_PENDING,
            },
        )

        payload = IDCardService._build_payload("STUDENT", student_profile.id, card.id, ID_CARD_STATUS_ISSUED)
        token = IDCardService._build_qr_token(payload)

        qr_file = build_qr_image_file(token, f"student_{student_profile.id}_qr.png")
        pdf_file_content = IDCardService._build_pdf_content(
            entity_type="STUDENT",
            full_name=student_profile.full_name,
            identity_code=student_profile.register_number,
            department_name=student_profile.department.name,
            card_number=card.card_number,
        )

        card.qr_token = token
        card.qr_image.save(qr_file.name, qr_file, save=False)
        card.pdf_file.save(f"student_{student_profile.id}_id_card.pdf", pdf_file_content, save=False)
        card.generated_by = generated_by
        card.generated_at = timezone.now()
        card.status = ID_CARD_STATUS_READY
        card.revoked_at = None
        card.save()
        EventService.emit_id_card_generated("STUDENT", card.card_number, student_profile.user.email)

        return card

    @staticmethod
    def generate_faculty_id_card(faculty_profile, generated_by):
        if not ConfigService.get_bool("onboarding.features.enable_id_card_generation", True):
            raise ValueError("ID card generation is disabled by configuration")

        card, _ = FacultyIDCard.objects.get_or_create(
            faculty_profile=faculty_profile,
            defaults={
                "card_number": IDCardService._build_card_number("FAC", str(faculty_profile.id)),
                "status": ID_CARD_STATUS_PENDING,
            },
        )

        payload = IDCardService._build_payload("FACULTY", faculty_profile.id, card.id, ID_CARD_STATUS_ISSUED)
        token = IDCardService._build_qr_token(payload)

        qr_file = build_qr_image_file(token, f"faculty_{faculty_profile.id}_qr.png")
        pdf_file_content = IDCardService._build_pdf_content(
            entity_type="FACULTY",
            full_name=faculty_profile.full_name,
            identity_code=str(faculty_profile.id),
            department_name=faculty_profile.department.name if faculty_profile.department else "N/A",
            card_number=card.card_number,
        )

        card.qr_token = token
        card.qr_image.save(qr_file.name, qr_file, save=False)
        card.pdf_file.save(f"faculty_{faculty_profile.id}_id_card.pdf", pdf_file_content, save=False)
        card.generated_by = generated_by
        card.generated_at = timezone.now()
        card.status = ID_CARD_STATUS_READY
        card.revoked_at = None
        card.save()
        EventService.emit_id_card_generated("FACULTY", card.card_number, faculty_profile.user.email)

        return card

    @staticmethod
    def revoke_student_id_card(student_profile):
        card = StudentIDCard.objects.filter(student_profile=student_profile).first()
        if not card:
            return None
        card.status = ID_CARD_STATUS_REVOKED
        card.revoked_at = timezone.now()
        card.save(update_fields=["status", "revoked_at"])
        return card

    @staticmethod
    def revoke_faculty_id_card(faculty_profile):
        card = FacultyIDCard.objects.filter(faculty_profile=faculty_profile).first()
        if not card:
            return None
        card.status = ID_CARD_STATUS_REVOKED
        card.revoked_at = timezone.now()
        card.save(update_fields=["status", "revoked_at"])
        return card

    @staticmethod
    def issue_card(card):
        card.status = ID_CARD_STATUS_ISSUED
        card.issued_at = timezone.now()
        card.save(update_fields=["status", "issued_at"])
        return card

    @staticmethod
    def verify_qr_token(token):
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        entity_type = payload.get("entity_type")
        card_id = payload.get("card_id")

        if entity_type == "STUDENT":
            card = StudentIDCard.objects.select_related("student_profile", "student_profile__department").filter(id=card_id).first()
        elif entity_type == "FACULTY":
            card = FacultyIDCard.objects.select_related("faculty_profile", "faculty_profile__department").filter(id=card_id).first()
        else:
            return {"is_valid": False, "message": "Invalid entity type in token"}

        if not card:
            return {"is_valid": False, "message": "Card not found"}

        if card.status == ID_CARD_STATUS_REVOKED:
            return {"is_valid": False, "message": "Card revoked"}

        if payload.get("card_status") != ID_CARD_STATUS_ISSUED:
            return {"is_valid": False, "message": "Token card status is invalid"}

        if card.status != ID_CARD_STATUS_ISSUED:
            return {"is_valid": False, "message": "Card is not in issued state"}

        return {
            "is_valid": True,
            "entity_type": entity_type,
            "card_number": card.card_number,
            "status": card.status,
            "payload": json.dumps(payload),
        }
