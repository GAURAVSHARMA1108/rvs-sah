import io
import re
import base64
from PIL import Image, ImageEnhance, ImageFilter

try:
    import pytesseract
except ImportError:
    pytesseract = None


def solve_captcha_from_base64(b64_str: str) -> str:
    """
    Decodes base64 captcha image, applies contrast/threshold pre-processing,
    and runs local OCR to extract the 6-character captcha code.
    Returns cleaned alphanumeric code or empty string.
    """
    if not b64_str:
        return ""

    try:
        # Strip data URL prefix if present
        if ',' in b64_str:
            b64_str = b64_str.split(',', 1)[1]

        img_bytes = base64.b64decode(b64_str)
        img = Image.open(io.BytesIO(img_bytes)).convert('L')  # Convert to Grayscale

        # Upscale image for better character boundary detection
        w, h = img.size
        img = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Binary thresholding to eliminate noise lines and gray artifacts
        threshold = 140
        img = img.point(lambda p: 255 if p > threshold else 0)

        # Smooth edges
        img = img.filter(ImageFilter.SMOOTH_MORE)

        if pytesseract:
            # PSM 8: Treat the image as a single word
            custom_config = r'--psm 8 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            raw_text = pytesseract.image_to_string(img, config=custom_config)
            cleaned = re.sub(r'[^A-Za-z0-9]', '', raw_text)
            return cleaned[:8].strip()
        else:
            return ""

    except Exception as e:
        print(f"[OCR Solver Error] Failed to solve captcha: {e}")
        return ""
