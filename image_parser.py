"""
image_parser.py
===============
Extracts Lightroom Mobile slider values from screenshots using OCR (Tesseract)
and computer-vision helpers for HSL colour tabs and point-curve screens.
"""

import io
import re
from collections import Counter, defaultdict

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2
    import numpy as np
except Exception:          # pragma: no cover
    cv2 = None
    np  = None

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except Exception:          # pragma: no cover
    pytesseract = None
    class TesseractNotFoundError(Exception):
        pass

from lightroom_schema import DISPLAY_TEMPLATE


NUMBER_RE = re.compile(r"[-+]?\s*\d+(?:[.,]\d+)?")

OCR_CONFIGS = [
    "--oem 3 --psm 6",
    "--oem 3 --psm 11",
    "--oem 3 --psm 4",
    "--oem 3 --psm 12",
]

FIELD_ALIASES = {
    # Light
    "Exposure":       ["exposure"],
    "Contrast":       ["contrast"],
    "Highlights":     ["highlights"],
    "Shadows":        ["shadows"],
    "Whites":         ["whites"],
    "Blacks":         ["blacks"],
    # Effects
    "Texture":        ["texture"],
    "Clarity":        ["clarity"],
    "Dehaze":         ["dehaze"],
    "Vibrance":       ["vibrance"],
    "Saturation":     ["saturation"],
    "Grain Amount":   ["grainamount", "amount"],
    "Grain Size":     ["grainsize"],
    "Grain Roughness":["grainroughness", "grainfrequency", "roughness"],
    # HSL colours (matched when on the correct HSL sub-screen)
    "Red Hue":              ["redhue"],
    "Red Saturation":       ["redsaturation"],
    "Red Luminance":        ["redluminance"],
    "Orange Hue":           ["orangehue"],
    "Orange Saturation":    ["orangesaturation"],
    "Orange Luminance":     ["orangeluminance"],
    "Yellow Hue":           ["yellowhue"],
    "Yellow Saturation":    ["yellowsaturation"],
    "Yellow Luminance":     ["yellowluminance"],
    "Green Hue":            ["greenhue"],
    "Green Saturation":     ["greensaturation"],
    "Green Luminance":      ["greenluminance"],
    "Cyan Hue":             ["cyanhue", "aquahue"],
    "Cyan Saturation":      ["cyansaturation", "aquasaturation"],
    "Cyan Luminance":       ["cyanluminance", "aqualuminance"],
    "Blue Hue":             ["bluehue"],
    "Blue Saturation":      ["bluesaturation"],
    "Blue Luminance":       ["blueluminance"],
    "Purple Hue":           ["purplehue"],
    "Purple Saturation":    ["purplesaturation"],
    "Purple Luminance":     ["purpleluminance"],
    "Magenta Hue":          ["magentahue"],
    "Magenta Saturation":   ["magentasaturation"],
    "Magenta Luminance":    ["magentaluminance"],
}

SECTION_BY_FIELD = {
    field: section
    for section, values in DISPLAY_TEMPLATE.items()
    if isinstance(values, dict)
    for field in values
}


def _normalize_text(text):
    return (
        str(text).lower()
        .replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
        .replace("—", "-").replace("–", "-")
        .replace(" ", "").replace(":", "").replace("_", "")
    )


def _extract_number(text):
    text = str(text).replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    m = NUMBER_RE.search(text)
    if not m:
        return None
    raw = m.group().replace(" ", "").replace(",", ".")
    try:
        n = float(raw)
    except ValueError:
        return None
    return int(n) if n.is_integer() and "." not in raw else n


def _empty_result():
    return {"Light": {}, "Effects": {}, "HSL": {}, "Curves": {}}


def _assign(result, field, value):
    section = SECTION_BY_FIELD.get(field)
    if section and section != "Curves" and value is not None:
        result[section][field] = value


# ---------------------------------------------------------------------------
# Computer-vision helpers
# ---------------------------------------------------------------------------

def _pil_to_cv(image):
    if cv2 is None or np is None:
        return None
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _classify_hue(hue_0_180):
    """Map an OpenCV hue (0–180) to a Lightroom HSL colour name."""
    deg = float(hue_0_180) * 2
    if deg < 15 or deg >= 345: return "Red"
    if deg < 45:  return "Orange"
    if deg < 75:  return "Yellow"
    if deg < 150: return "Green"
    if deg < 195: return "Cyan"
    if deg < 245: return "Blue"
    if deg < 285: return "Purple"
    return "Magenta"


def detect_selected_hsl_color(image):
    """Detect the active HSL colour swatch in a Lightroom Mobile landscape screenshot."""
    cv_img = _pil_to_cv(image)
    if cv_img is None:
        return None
    h, w = cv_img.shape[:2]
    if w <= h:
        return None

    crop = cv_img[0:int(h * 0.32), int(w * 0.55):w]
    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    candidates = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        x, y, cw, ch = stats[idx, :4]
        if not (50 < area < 3000 and 10 < cw < 80 and 10 < ch < 80):
            continue
        if not (h * 0.10 < y < h * 0.30):
            continue
        hue_vals = hsv[:, :, 0][labels == idx]
        if hue_vals.size:
            candidates.append((area, _classify_hue(float(np.median(hue_vals)))))

    if not candidates:
        return None
    return max(candidates, key=lambda t: t[0])[1]


def _detect_curve_channel(image):
    """Detect the active curve channel (Red/Green/Blue) in a point-curve screenshot."""
    cv_img = _pil_to_cv(image)
    if cv_img is None:
        return None
    h, w = cv_img.shape[:2]
    if h <= w:
        return None

    bottom = cv_img[int(h * 0.86):h, :]
    hsv    = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
    mask   = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    candidates = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        x, y, cw, ch = stats[idx, :4]
        if not (40 < area < 3000 and 10 < cw < 80 and 10 < ch < 80):
            continue
        hue_vals = hsv[:, :, 0][labels == idx]
        if hue_vals.size:
            candidates.append((area, _classify_hue(float(np.median(hue_vals)))))

    if not candidates:
        return None
    color = max(candidates, key=lambda t: t[0])[1]
    return color if color in {"Red", "Green", "Blue"} else None


def _normalize_curve_points(raw_points, width, height):
    x_min, x_max = width * 0.073, width * 0.927
    y_min, y_max = height * 0.31,  height * 0.77
    normalized = []
    for x, y in raw_points:
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            continue
        nx = round((x - x_min) / (x_max - x_min) * 255)
        ny = round((y_max - y) / (y_max - y_min) * 255)
        normalized.append((max(0, min(255, nx)), max(0, min(255, ny))))

    if not normalized:
        return []

    by_x = {}
    for x, y in normalized:
        by_x[x] = y
    ordered = [(x, by_x[x]) for x in sorted(by_x)]

    if ordered[0][0] > 8:
        ordered.insert(0, (0, 0))
    else:
        ordered[0] = (0, ordered[0][1])
    if ordered[-1][0] < 247:
        ordered.append((255, 255))
    else:
        ordered[-1] = (255, ordered[-1][1])

    return [f"{x}, {y}" for x, y in ordered]


def detect_curve_points(image):
    """Best-effort point-curve extraction from a Lightroom Mobile screenshot."""
    channel = _detect_curve_channel(image)
    if channel is None or cv2 is None or np is None:
        return {}

    cv_img = _pil_to_cv(image)
    h, w   = cv_img.shape[:2]
    gray   = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    x_min, x_max = int(w * 0.04), int(w * 0.96)
    y_min, y_max = int(h * 0.30), int(h * 0.79)
    crop = gray[y_min:y_max, x_min:x_max]

    bright   = cv2.inRange(crop, 205, 255)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not (80 <= area <= 1800):
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        if not (10 <= cw <= 45 and 10 <= ch <= 45):
            continue
        peri = cv2.arcLength(contour, True)
        if peri == 0:
            continue
        if 4 * np.pi * area / (peri * peri) < 0.35:
            continue
        candidates.append((x + x_min + cw / 2, y + y_min + ch / 2))

    points = _normalize_curve_points(candidates, w, h)
    if len(points) < 3:
        return {}
    return {channel: points}


# ---------------------------------------------------------------------------
# OCR preprocessing
# ---------------------------------------------------------------------------

def preprocess(image):
    """Generate multiple enhanced variants for multi-pass OCR."""
    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(2.5)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)

    variants = [
        gray,
        ImageOps.invert(gray),
        gray.filter(ImageFilter.MedianFilter(size=3)),
        ImageEnhance.Contrast(gray).enhance(1.5),
    ]

    w, h  = image.size
    crops = []
    if w > h:   # landscape — controls on right half
        crops = [
            (int(w * 0.48), 0,           w, h),
            (int(w * 0.55), 0,           w, int(h * 0.92)),
            (int(w * 0.50), int(h*0.05), w, int(h * 0.90)),
        ]
    else:       # portrait — controls in lower portion
        crops = [
            (0, int(h * 0.40), w, h),
            (0, int(h * 0.30), w, int(h * 0.88)),
        ]

    result = []
    scale  = 2
    for variant in variants:
        result.append(variant.resize((variant.width * scale, variant.height * scale), Image.LANCZOS))
        for box in crops:
            crop = variant.crop(box)
            result.append(crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS))
    return result


# ---------------------------------------------------------------------------
# Text parsing
# ---------------------------------------------------------------------------

def parse_text(text, image=None):
    result       = _empty_result()
    compact_text = _normalize_text(text)
    hsl_color    = detect_selected_hsl_color(image) if image is not None else None

    # Detect panel type from OCR text
    is_grain_screen = "grain" in compact_text or "roughness" in compact_text
    is_hsl_screen   = hsl_color is not None or any(
        kw in compact_text for kw in ("hue", "saturation", "luminance")
    )

    for raw_line in str(text).splitlines():
        line  = _normalize_text(raw_line)
        value = _extract_number(raw_line)
        if value is None:
            continue

        # -- HSL shortcut: if we know the active colour, map hue/sat/lum directly --
        if hsl_color:
            if "hue" in line and "saturation" not in line:
                _assign(result, f"{hsl_color} Hue", value); continue
            if "saturation" in line:
                _assign(result, f"{hsl_color} Saturation", value); continue
            if "luminance" in line:
                _assign(result, f"{hsl_color} Luminance", value); continue

        # -- Grain screen: map by positional label (Amount / Size / Roughness) --
        if is_grain_screen:
            if "amount" in line and "grain" not in line:
                _assign(result, "Grain Amount", value); continue
            if "size" in line:
                _assign(result, "Grain Size", value); continue
            if "roughness" in line:
                _assign(result, "Grain Roughness", value); continue

        # -- Generic alias matching --
        for field, aliases in FIELD_ALIASES.items():
            if any(alias in line for alias in aliases):
                _assign(result, field, value)
                break

    return result


# ---------------------------------------------------------------------------
# OCR runner
# ---------------------------------------------------------------------------

def _ocr_image(image):
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed.")
    texts = []
    for variant in preprocess(image):
        for config in OCR_CONFIGS:
            try:
                texts.append(pytesseract.image_to_string(variant, config=config))
            except Exception:
                pass
    return "\n".join(texts)


def _merge_results(results):
    merged          = _empty_result()
    values_by_field = defaultdict(list)

    for r in results:
        for section, vals in r.items():
            if section == "Curves":
                for key, points in vals.items():
                    if points:
                        merged["Curves"][key] = points
                continue
            for key, val in vals.items():
                values_by_field[(section, key)].append(val)

    for (section, key), vals in values_by_field.items():
        merged[section][key] = Counter(vals).most_common(1)[0][0]

    return merged


def _fill_display_defaults(data):
    from copy import deepcopy
    final = deepcopy(DISPLAY_TEMPLATE)
    for section, vals in data.items():
        if not isinstance(vals, dict):
            continue
        final.setdefault(section, {})
        final[section].update(vals)
    return final


def _open_image(file):
    if hasattr(file, "stream"):
        return Image.open(file.stream).convert("RGB")
    if hasattr(file, "read"):
        return Image.open(file).convert("RGB")
    return Image.open(io.BytesIO(file)).convert("RGB")


def extract_from_images(files):
    """
    Run OCR + CV on a list of image files and return a display-shaped preset.
    """
    parsed_results = []
    sources        = []
    warnings       = []

    for idx, file in enumerate(files, start=1):
        image       = _open_image(file)
        source_name = getattr(file, "filename", None) or f"image_{idx}"

        # Try curve extraction first (portrait curve screens)
        curve_result = detect_curve_points(image)
        if curve_result:
            parsed_results.append({"Curves": curve_result, "Light": {}, "Effects": {}, "HSL": {}})
            sources.append({"name": source_name, "type": "curve", "fields": list(curve_result)})
            continue

        try:
            text = _ocr_image(image)
        except TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract OCR is not installed or not in PATH. "
                "Add 'tesseract-ocr' and 'tesseract-ocr-eng' to Aptfile."
            )

        parsed     = parse_text(text, image=image)
        field_count = sum(len(v) for v in parsed.values() if isinstance(v, dict))
        parsed_results.append(parsed)
        sources.append({"name": source_name, "type": "ocr", "fields": field_count})

        if field_count == 0:
            warnings.append(f"No Lightroom values detected in {source_name}.")

    merged = _merge_results(parsed_results)
    final  = _fill_display_defaults(merged)

    return {
        **final,
        "sources":  sources,
        "warnings": warnings,
        "meta":     {"success": True},
    }
