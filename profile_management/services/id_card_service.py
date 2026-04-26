import io
import qrcode
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.conf import settings
from profile_management.models import StudentProfile, FacultyProfile, IDCardTemplate
import os

class IDCardService:
    # ID Card Size: 85.6mm x 54mm (Standard CR80)
    CARD_WIDTH = 85.6 * mm
    CARD_HEIGHT = 54 * mm

    # ─── Colors (defaults — overridden at runtime from IDCardTemplate) ────────
    _STUDENT_PRIMARY = "#2563eb"
    _FACULTY_PRIMARY = "#059669"
    _BG              = "#f8fafc"
    _GREY            = "#6b7280"
    _LIGHT_GREY      = "#d1d5db"

    @staticmethod
    def _get_colors(is_student: bool):
        """
        Return a dict of hex color strings for the card type.
        Reads live from DB so admin changes take effect immediately.
        """
        tpl = IDCardTemplate.get_or_create_default()
        if is_student:
            return {
                "primary":     tpl.student_primary_color,
                "header_text": tpl.student_header_text_color,
                "bg":          tpl.student_background_color,
                "text":        tpl.student_text_color,
                "label":       tpl.student_label_color,
            }
        return {
            "primary":     tpl.faculty_primary_color,
            "header_text": tpl.faculty_header_text_color,
            "bg":          tpl.faculty_background_color,
            "text":        tpl.faculty_text_color,
            "label":       tpl.faculty_label_color,
        }

    # ─── Public API ───────────────────────────────────────────────────────────

    @staticmethod
    def generate_student_pdf(student, orientation='landscape'):
        w, h = IDCardService._dims(orientation)
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(w, h))
        IDCardService._front(c, student, is_student=True, orientation=orientation)
        c.showPage()
        IDCardService._back_student(c, student, orientation=orientation)
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    @staticmethod
    def generate_faculty_pdf(faculty, orientation='landscape'):
        w, h = IDCardService._dims(orientation)
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(w, h))
        IDCardService._front(c, faculty, is_student=False, orientation=orientation)
        c.showPage()
        IDCardService._back_faculty(c, faculty, orientation=orientation)
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    @staticmethod
    def _draw_card(c, profile, is_student=True, orientation='landscape'):
        """Legacy entry-point used by BulkIDCardPDFView (draws front only on current page)."""
        IDCardService._front(c, profile, is_student=is_student, orientation=orientation)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _dims(orientation):
        if orientation == 'landscape':
            return IDCardService.CARD_WIDTH, IDCardService.CARD_HEIGHT
        return IDCardService.CARD_HEIGHT, IDCardService.CARD_WIDTH

    @staticmethod
    def _draw_photo(c, profile, photo_x, photo_y, photo_size):
        c.setFillColor(colors.HexColor("#ffffff"))
        c.setStrokeColor(colors.HexColor(IDCardService._LIGHT_GREY))
        c.setLineWidth(0.4)
        c.rect(photo_x, photo_y, photo_size, photo_size, fill=1, stroke=1)
        if profile.profile_photo:
            try:
                if os.path.exists(profile.profile_photo.path):
                    img = ImageReader(profile.profile_photo.path)
                    c.drawImage(img, photo_x + 0.4*mm, photo_y + 0.4*mm,
                                photo_size - 0.8*mm, photo_size - 0.8*mm)
            except Exception:
                pass

    @staticmethod
    def _draw_qr(c, profile, is_student, cx, cy, size):
        """Draw a QR code centred at (cx, cy) with given size."""
        qr_data = (
            f"ID:{profile.id}|TYPE:{'STUDENT' if is_student else 'FACULTY'}"
            f"|REG:{profile.register_number if is_student else profile.id}"
        )
        qr = qrcode.QRCode(version=1, box_size=1, border=0)
        qr.add_data(qr_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        c.drawImage(ImageReader(qr_buf), cx - size/2, cy - size/2, size, size)

    @staticmethod
    def _draw_header(c, profile, is_student, width, height, header_h):
        clr = IDCardService._get_colors(is_student)
        primary = colors.HexColor(clr["primary"])
        c.setFillColor(primary)
        c.rect(0, height - header_h, width, header_h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(clr["header_text"]))
        inst_name = getattr(profile, 'institution_name', 'COLLEGE MANAGEMENT SYSTEM')
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(width/2, height - 7*mm, str(inst_name)[:40].upper())
        c.setFont("Helvetica", 5.5)
        card_type = "STUDENT IDENTITY CARD" if is_student else "FACULTY IDENTITY CARD"
        c.drawCentredString(width/2, height - 11.5*mm, card_type)

    @staticmethod
    def _draw_footer_line(c, primary_color, width):
        c.setStrokeColor(primary_color)
        c.setLineWidth(1*mm)
        c.line(0, 0, width, 0)

    @staticmethod
    def _truncate(text, max_chars):
        text = str(text)
        return text if len(text) <= max_chars else text[:max_chars - 1] + "…"

    # ─── FRONT (Landscape) ────────────────────────────────────────────────────

    @staticmethod
    def _front_landscape(c, profile, is_student):
        w, h = IDCardService.CARD_WIDTH, IDCardService.CARD_HEIGHT
        clr = IDCardService._get_colors(is_student)
        primary = colors.HexColor(clr["primary"])

        c.setFillColor(colors.HexColor(clr["bg"]))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        IDCardService._draw_header(c, profile, is_student, w, h, 14*mm)

        photo_size = 24*mm
        photo_x, photo_y = 4*mm, h - 14*mm - photo_size - 3*mm
        IDCardService._draw_photo(c, profile, photo_x, photo_y, photo_size)

        dx, dy = photo_x + photo_size + 4*mm, h - 20*mm

        c.setFillColor(colors.HexColor(clr["text"]))
        c.setFont("Helvetica-Bold", 9)
        c.drawString(dx, dy, IDCardService._truncate(profile.full_name.upper(), 22))

        dy -= 4.5*mm
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(primary)
        sub = profile.designation if not is_student else f"Year {profile.year}  |  Sem {profile.semester}"
        c.drawString(dx, dy, IDCardService._truncate(sub, 28))

        dy -= 6*mm
        if is_student:
            rows = [
                ("Reg No", profile.register_number),
                ("Dept",   profile.department.name if profile.department else "—"),
                ("Course", profile.course.name if profile.course else "—"),
            ]
        else:
            rows = [
                ("Email",  profile.user.email or "—"),
                ("Dept",   profile.department.name if profile.department else "—"),
                ("Joined", str(profile.joining_date)),
            ]

        for label, value in rows:
            c.setFont("Helvetica-Bold", 5.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawString(dx, dy, label.upper())
            c.setFont("Helvetica", 6)
            c.setFillColor(colors.HexColor(clr["text"]))
            c.drawString(dx + 14*mm, dy, IDCardService._truncate(value, 22))
            dy -= 4*mm

        IDCardService._draw_footer_line(c, primary, w)

    # ─── FRONT (Portrait) ─────────────────────────────────────────────────────

    @staticmethod
    def _front_portrait(c, profile, is_student):
        w, h = IDCardService.CARD_HEIGHT, IDCardService.CARD_WIDTH
        clr = IDCardService._get_colors(is_student)
        primary = colors.HexColor(clr["primary"])

        c.setFillColor(colors.HexColor(clr["bg"]))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        IDCardService._draw_header(c, profile, is_student, w, h, 15*mm)

        photo_size = 22*mm
        photo_x = (w - photo_size) / 2
        photo_y = h - 15*mm - photo_size - 3*mm
        IDCardService._draw_photo(c, profile, photo_x, photo_y, photo_size)

        cy = photo_y - 5*mm
        c.setFillColor(colors.HexColor(clr["text"]))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w/2, cy, IDCardService._truncate(profile.full_name.upper(), 22))

        cy -= 4.5*mm
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(primary)
        sub = profile.designation if not is_student else f"Year {profile.year}  |  Sem {profile.semester}"
        c.drawCentredString(w/2, cy, IDCardService._truncate(sub, 28))

        cy -= 6*mm
        if is_student:
            rows = [
                ("Reg No", profile.register_number),
                ("Dept",   profile.department.name if profile.department else "—"),
            ]
        else:
            rows = [
                ("Email", profile.user.email or "—"),
                ("Dept",  profile.department.name if profile.department else "—"),
            ]

        for label, value in rows:
            c.setFont("Helvetica-Bold", 5.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawCentredString(w/2, cy, f"{label.upper()}: {IDCardService._truncate(value, 24)}")
            cy -= 4*mm

        IDCardService._draw_footer_line(c, primary, w)

    # ─── FRONT dispatcher ─────────────────────────────────────────────────────

    @staticmethod
    def _front(c, profile, is_student, orientation):
        if orientation == 'landscape':
            IDCardService._front_landscape(c, profile, is_student)
        else:
            IDCardService._front_portrait(c, profile, is_student)

    # ─── BACK (Student) ───────────────────────────────────────────────────────

    @staticmethod
    def _back_student(c, student, orientation):
        w, h = IDCardService._dims(orientation)
        clr = IDCardService._get_colors(True)
        primary = colors.HexColor(clr["primary"])
        is_landscape = orientation == 'landscape'

        c.setFillColor(colors.HexColor(clr["bg"]))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        c.setFillColor(primary)
        c.rect(0, h - 4*mm, w, 4*mm, fill=1, stroke=0)

        if is_landscape:
            qr_size = 22*mm
            qr_cx = w - qr_size/2 - 5*mm
            qr_cy = h/2 - 2*mm
            IDCardService._draw_qr(c, student, True, qr_cx, qr_cy, qr_size)

            c.setFont("Helvetica", 4.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawCentredString(qr_cx, qr_cy - qr_size/2 - 2*mm, "SCAN TO VERIFY")

            tx, ty = 5*mm, h - 9*mm
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(primary)
            c.drawString(tx, ty, "CONTACT DETAILS")

            ty -= 5*mm
            rows = [
                ("Address",    student.address or "—"),
                ("Guardian",   student.guardian_name or "—"),
                ("Relation",   student.guardian_relationship or "—"),
                ("Parent Ph.", student.guardian_phone or "—"),
            ]
            for label, value in rows:
                c.setFont("Helvetica-Bold", 5.5)
                c.setFillColor(colors.HexColor(clr["label"]))
                c.drawString(tx, ty, label.upper())
                c.setFont("Helvetica", 6)
                c.setFillColor(colors.HexColor(clr["text"]))
                if label == "Address" and len(str(value)) > 20:
                    line1 = str(value)[:22]
                    line2 = str(value)[22:44]
                    c.drawString(tx + 16*mm, ty, line1)
                    ty -= 3.5*mm
                    c.drawString(tx + 16*mm, ty, line2)
                else:
                    c.drawString(tx + 16*mm, ty, IDCardService._truncate(value, 22))
                ty -= 4.5*mm

        else:
            qr_size = 20*mm
            IDCardService._draw_qr(c, student, True, w/2, h - 9*mm - qr_size/2, qr_size)

            c.setFont("Helvetica", 4.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawCentredString(w/2, h - 9*mm - qr_size - 2*mm, "SCAN TO VERIFY")

            ty = h - 9*mm - qr_size - 8*mm
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(primary)
            c.drawCentredString(w/2, ty, "CONTACT DETAILS")

            ty -= 5*mm
            rows = [
                ("Address",    student.address or "—"),
                ("Guardian",   student.guardian_name or "—"),
                ("Parent Ph.", student.guardian_phone or "—"),
            ]
            for label, value in rows:
                c.setFont("Helvetica-Bold", 5.5)
                c.setFillColor(colors.HexColor(clr["label"]))
                c.drawCentredString(w/2, ty, f"{label.upper()}: {IDCardService._truncate(value, 24)}")
                ty -= 4.5*mm

        c.setFont("Helvetica-Oblique", 4.5)
        c.setFillColor(colors.HexColor(clr["label"]))
        c.drawCentredString(w/2, 3*mm, "This card is the property of the institution. If found, please return.")

        IDCardService._draw_footer_line(c, primary, w)

    # ─── BACK (Faculty) ───────────────────────────────────────────────────────

    @staticmethod
    def _back_faculty(c, faculty, orientation):
        w, h = IDCardService._dims(orientation)
        clr = IDCardService._get_colors(False)
        primary = colors.HexColor(clr["primary"])
        is_landscape = orientation == 'landscape'

        c.setFillColor(colors.HexColor(clr["bg"]))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        c.setFillColor(primary)
        c.rect(0, h - 4*mm, w, 4*mm, fill=1, stroke=0)

        if is_landscape:
            qr_size = 22*mm
            qr_cx = w - qr_size/2 - 5*mm
            qr_cy = h/2 - 2*mm
            IDCardService._draw_qr(c, faculty, False, qr_cx, qr_cy, qr_size)

            c.setFont("Helvetica", 4.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawCentredString(qr_cx, qr_cy - qr_size/2 - 2*mm, "SCAN TO VERIFY")

            tx, ty = 5*mm, h - 9*mm
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(primary)
            c.drawString(tx, ty, "FACULTY DETAILS")

            ty -= 5*mm
            rows = [
                ("Specialization", faculty.specialization or "—"),
                ("Qualifications", faculty.qualifications or "—"),
                ("Office Hours",   faculty.office_hours or "—"),
                ("Teaching Load",  f"{faculty.teaching_load} hrs/week"),
            ]
            for label, value in rows:
                c.setFont("Helvetica-Bold", 5.5)
                c.setFillColor(colors.HexColor(clr["label"]))
                c.drawString(tx, ty, label.upper())
                c.setFont("Helvetica", 6)
                c.setFillColor(colors.HexColor(clr["text"]))
                c.drawString(tx + 22*mm, ty, IDCardService._truncate(value, 20))
                ty -= 4.5*mm
        else:
            qr_size = 20*mm
            IDCardService._draw_qr(c, faculty, False, w/2, h - 9*mm - qr_size/2, qr_size)

            c.setFont("Helvetica", 4.5)
            c.setFillColor(colors.HexColor(clr["label"]))
            c.drawCentredString(w/2, h - 9*mm - qr_size - 2*mm, "SCAN TO VERIFY")

            ty = h - 9*mm - qr_size - 8*mm
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(primary)
            c.drawCentredString(w/2, ty, "FACULTY DETAILS")

            ty -= 5*mm
            rows = [
                ("Specialization", faculty.specialization or "—"),
                ("Office Hours",   faculty.office_hours or "—"),
            ]
            for label, value in rows:
                c.setFont("Helvetica-Bold", 5.5)
                c.setFillColor(colors.HexColor(clr["label"]))
                c.drawCentredString(w/2, ty, f"{label.upper()}: {IDCardService._truncate(value, 24)}")
                ty -= 4.5*mm

        c.setFont("Helvetica-Oblique", 4.5)
        c.setFillColor(colors.HexColor(clr["label"]))
        c.drawCentredString(w/2, 3*mm, "This card is the property of the institution. If found, please return.")

        IDCardService._draw_footer_line(c, primary, w)


