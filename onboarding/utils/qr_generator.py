from io import BytesIO

import qrcode
from django.core.files.base import ContentFile


def build_qr_image_file(payload_text, file_name):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(payload_text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ContentFile(buffer.read(), name=file_name)
