from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, ImageOps

from .models import CropResult, Face


def valid_face_box(face: Face) -> bool:
    if face.image_width <= 0 or face.image_height <= 0:
        return False
    if not (0 <= face.x1 < face.x2 <= face.image_width):
        return False
    if not (0 <= face.y1 < face.y2 <= face.image_height):
        return False
    width = face.x2 - face.x1
    height = face.y2 - face.y1
    if width < 48 or height < 48:
        return False
    ratio = width / height
    return not (ratio < 0.45 or ratio > 1.8)


def crop_face(image_bytes: bytes, face: Face, padding: float = 0.35) -> CropResult:
    with Image.open(BytesIO(image_bytes)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        scale_x = image.width / face.image_width
        scale_y = image.height / face.image_height
        x1 = face.x1 * scale_x
        y1 = face.y1 * scale_y
        x2 = face.x2 * scale_x
        y2 = face.y2 * scale_y
        width = x2 - x1
        height = y2 - y1
        pad_x = width * padding
        pad_y = height * padding
        box = (
            max(0, round(x1 - pad_x)),
            max(0, round(y1 - pad_y)),
            min(image.width, round(x2 + pad_x)),
            min(image.height, round(y2 + pad_y)),
        )
        crop = image.crop(box)
        if crop.width > 800 or crop.height > 800:
            crop.thumbnail((800, 800), Image.Resampling.LANCZOS)
        output = BytesIO()
        crop.save(output, format="JPEG", quality=92, optimize=True)
        data = output.getvalue()
        return CropResult(
            image_bytes=data,
            content_hash=hashlib.sha256(data).hexdigest(),
            width=crop.width,
            height=crop.height,
        )
