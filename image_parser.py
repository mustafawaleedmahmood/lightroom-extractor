import io
import re
from collections import Counter, defaultdict

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - optional computer-vision enhancement
    cv2 = None
    np = None

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except Exception:  # pragma: no cover - deployment should install pytesseract
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
    "Exposure": ["exposure"],
    "Contrast": ["contrast"],
    "Highlights": ["highlights"],
    "Shadows": ["shadows"],
    "Whites": ["whites"],
    "Blacks": ["blacks"],
    "Texture": ["texture"],
    "Clarity": ["clarity"],
    "Dehaze": ["dehaze"],
    "Vibrance": ["vibrance"],
    "Saturation": ["saturation"],
    "Grain Amount": ["grainamount"],
    "Grain Size": ["grainsize"],
    "Grain Roughness": ["grainroughness", "grainfrequency"],
    "Red Hue": ["redhue"],
    "Red Saturation": ["redsaturation"],
    "Red Luminance": ["redluminance"],
    "Orange Hue": ["orangehue"],
    "Orange Saturation": ["orangesaturation"],
    "Orange Luminance": ["orangeluminance"],
    "Yellow Hue": ["yellowhue"],
    "Yellow Saturation": ["yellowsaturation"],
    "Yellow Luminance": ["yellowluminance"],
    "Green Hue": ["greenhue"],
    "Green Saturation": ["greensaturation"],
    "Green Luminance": ["greenluminance"],
    "Cyan Hue": ["cyanhue", "aquahue"],
    "Cyan Saturation": ["cyansaturation", "aquasaturation"],
    "Cyan Luminance": ["cyanluminance", "aqualuminance"],
    "Blue Hue": ["bluehue"],
    "Blue Saturation": ["bluesaturation"],
    "Blue Luminance": ["blueluminance"],
    "Purple Hue": ["purplehue"],
    "Purple Saturation": ["purplesaturation"],
    "Purple Luminance": ["purpleluminance"],
    "Magenta Hue": ["magentahue"],
    "Magenta Saturation": ["magentasaturation"],
    "Magenta Luminance": ["magentaluminance"],
}

SECTION_BY_FIELD = {}
for _section_name, _section_values in DISPLAY_TEMPLATE.items():
    if isinstance(_section_values, dict):
        for _field_name in _section_values:
            SECTION_BY_FIELD[_field_name] = _section_name


def _normalize_text(text):
    return (
        str(text).lower()
        .replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace(" ", "")
        .replace(":", "")
        .replace("_", "")
    )


def _extract_number(text):
    match = NUMBER_RE.search(str(text).replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-"))
    if not match:
        return None
    raw = match.group().replace(" ", "").replace(",", ".")
    try:
        number = float(raw)
    except ValueError:
        return None
    return int(number) if number.is_integer() and "." not in raw else number


def _empty_result():
    return {
        "Light": {},
        "Effects": {},
        "HSL": {},
        "Curves": {},
    }


def _assign(result, field, value):
    section = SECTION_BY_FIELD.get(field)
    if section and section != "Curves" and value is not None:
        result[section][field] = value


def _classify_hue(hue):
    degrees = float(hue) * 2
    if degrees < 15 or degrees >= 345:
        return "Red"
    if degrees < 45:
        return "Orange"
    if degrees < 75:
        return "Yellow"
    if degrees < 150:
        return "Green"
    if degrees < 195:
        return "Cyan"
    if degrees < 245:
        return "Blue"
    if degrees < 285:
        return "Purple"
    return "Magenta"


def _pil_to_cv(image):
    if cv2 is None or np is None:
        return None
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def detect_selected_hsl_color(image):
    """Detect the active HSL swatch in Lightroom Mobile landscape screenshots."""
    cv_image = _pil_to_cv(image)
    if cv_image is None:
        return None

    height, width = cv_image.shape[:2]
    if width <= height:
        return None

    crop = cv_image[0:int(height * 0.32), int(width * 0.55):width]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    candidates = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        x, y, comp_w, comp_h = stats[idx, :4]
        if not (50 < area < 3000 and 10 < comp_w < 80 and 10 < comp_h < 80):
            continue
        if not (height * 0.10 < y < height * 0.30):
            continue
        hue_values = hsv[:, :, 0][labels == idx]
        if hue_values.size:
            candidates.append((area, _classify_hue(float(np.median(hue_values)))))

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _detect_curve_channel(image):
    cv_image = _pil_to_cv(image)
    if cv_image is None:
        return None
    height, width = cv_image.shape[:2]
    if height <= width:
        return None

    bottom = cv_image[int(height * 0.86):height, :]
    hsv = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 90)).astype("uint8") * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    candidates = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        x, y, comp_w, comp_h = stats[idx, :4]
        if not (40 < area < 3000 and 10 < comp_w < 80 and 10 < comp_h < 80):
            continue
        hue_values = hsv[:, :, 0][labels == idx]
        if hue_values.size:
            candidates.append((area, _classify_hue(float(np.median(hue_values)))))

    if not candidates:
        return None

    color = max(candidates, key=lambda item: item[0])[1]
    if color in {"Red", "Green", "Blue"}:
        return color
    return None


def _normalize_curve_points(points, width, height):
    x_min, x_max = width * 0.073, width * 0.927
    y_min, y_max = height * 0.31, height * 0.77
    normalized = []
    for x, y in points:
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
    """
    Best-effort point-curve extraction for Lightroom Mobile curve screenshots.
    Parametric curve screenshots are intentionally not guessed because the exact
    CRS values are the hidden slider numbers, not the rendered curve shape.
    """
    channel = _detect_curve_channel(image)
    if channel is None or cv2 is None or np is None:
        return {}

    cv_image = _pil_to_cv(image)
    height, width = cv_image.shape[:2]
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    x_min, x_max = int(width * 0.04), int(width * 0.96)
    y_min, y_max = int(height * 0.30), int(height * 0.79)
    crop = gray[y_min:y_max, x_min:x_max]

    bright = cv2.inRange(crop, 205, 255)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not 80 <= area <= 1800:
            continue
        x, y, comp_w, comp_h = cv2.boundingRect(contour)
        if not 10 <= comp_w <= 45 or not 10 <= comp_h <= 45:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < 0.35:
            continue
        candidates.append((x + x_min + comp_w / 2, y + y_min + comp_h / 2))

    points = _normalize_curve_points(candidates, width, height)
    if len(points) < 3:
        return {}

    return {channel: points}


def preprocess(image):
    gray = ImageOps.grayscale(image)
    gray = ImageEnhance.Contrast(gray).enhance(2.2)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)
    variants = [
        gray,
        ImageOps.invert(gray),
        gray.filter(ImageFilter.MedianFilter(size=3)),
    ]

    crops = []
    width, height = image.size
    if width > height:
        crops.extend([
            (int(width * 0.50), 0, width, height),
            (int(width * 0.58), 0, width, int(height * 0.92)),
        ])
    else:
        crops.extend([
            (0, int(height * 0.45), width, height),
            (0, int(height * 0.30), width, int(height * 0.86)),
        ])

    final = []
    for variant in variants:
        final.append(variant.resize((variant.width * 2, variant.height * 2)))
        for box in crops:
            crop = variant.crop(box)
            final.append(crop.resize((crop.width * 2, crop.height * 2)))
    return final


def parse_text(text, image=None):
    result = _empty_result()
    compact_text = _normalize_text(text)
    hsl_color = detect_selected_hsl_color(image) if image is not None else None
    is_grain_screen = "grain" in compact_text or "roughness" in compact_text

    for raw_line in str(text).splitlines():
        line = _normalize_text(raw_line)
        value = _extract_number(raw_line)
        if value is None:
            continue

        if hsl_color:
            if "hue" in line:
                _assign(result, f"{hsl_color} Hue", value)
                continue
            if "saturation" in line:
                _assign(result, f"{hsl_color} Saturation", value)
                continue
            if "luminance" in line:
                _assign(result, f"{hsl_color} Luminance", value)
                continue

        if is_grain_screen:
            if "amount" in line:
                _assign(result, "Grain Amount", value)
                continue
            if "size" in line:
                _assign(result, "Grain Size", value)
                continue
            if "roughness" in line:
                _assign(result, "Grain Roughness", value)
                continue

        for field, aliases in FIELD_ALIASES.items():
            if any(alias in line for alias in aliases):
                _assign(result, field, value)
                break

    return result


def _ocr_image(image):
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")

    texts = []
    for variant in preprocess(image):
        for config in OCR_CONFIGS:
            texts.append(pytesseract.image_to_string(variant, config=config))
    return "\n".join(texts)


def _merge_results(results):
    merged = _empty_result()
    values_by_field = defaultdict(list)

    for result in results:
        for section, values in result.items():
            if section == "Curves":
                for key, points in values.items():
                    if points:
                        merged["Curves"][key] = points
                continue
            for key, value in values.items():
                values_by_field[(section, key)].append(value)

    for (section, key), values in values_by_field.items():
        merged[section][key] = Counter(values).most_common(1)[0][0]

    return merged


def _fill_display_defaults(data):
    final = {
        section: (values.copy() if isinstance(values, dict) else values)
        for section, values in DISPLAY_TEMPLATE.items()
    }
    for section, values in data.items():
        if not isinstance(values, dict):
            continue
        final.setdefault(section, {})
        final[section].update(values)
    return final


def _open_image(file):
    if hasattr(file, "stream"):
        return Image.open(file.stream).convert("RGB")
    if hasattr(file, "read"):
        return Image.open(file).convert("RGB")
    return Image.open(io.BytesIO(file)).convert("RGB")


def extract_from_images(files):
    parsed_results = []
    sources = []
    warnings = []

    for index, file in enumerate(files, start=1):
        image = _open_image(file)
        source_name = getattr(file, "filename", None) or f"image_{index}"

        curve_result = detect_curve_points(image)
        if curve_result:
            parsed_results.append({"Curves": curve_result})
            sources.append({"name": source_name, "type": "curve", "fields": list(curve_result)})
            continue

        try:
            text = _ocr_image(image)
        except TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract OCR is not installed or not available in PATH. "
                "Install the system package tesseract-ocr in addition to pytesseract."
            )

        parsed = parse_text(text, image=image)
        parsed_results.append(parsed)

        field_count = sum(len(values) for values in parsed.values() if isinstance(values, dict))
        sources.append({
            "name": source_name,
            "type": "ocr",
            "fields": field_count,
        })
        if field_count == 0:
            warnings.append(f"No Lightroom values were detected in {source_name}.")

    merged = _merge_results(parsed_results)
    final = _fill_display_defaults(merged)
    return {
        **final,
        "sources": sources,
        "warnings": warnings,
        "meta": {"success": True},
    }
    
