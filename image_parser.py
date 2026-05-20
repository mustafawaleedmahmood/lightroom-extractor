# image_parser.py
from __future__ import annotations

import io
import re
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Dict, Iterable, List, Optional, Tuple, Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

from lightroom_schema import DISPLAY_TEMPLATE

# =========================================================
# Text matching maps
# =========================================================

FIELD_ALIASES: Dict[str, Dict[str, List[str]]] = {
    "Light": {
        "Exposure": ["exposure", "exposure2012"],
        "Contrast": ["contrast", "contrast2012"],
        "Highlights": ["highlights", "highlights2012"],
        "Shadows": ["shadows", "shadows2012"],
        "Whites": ["whites", "whites2012"],
        "Blacks": ["blacks", "blacks2012"],
    },
    "Effects": {
        "Clarity": ["clarity", "clarity2012"],
        "Dehaze": ["dehaze"],
        "Texture": ["texture"],
        "Vibrance": ["vibrance"],
        "Saturation": ["saturation"],
        "Grain Amount": ["grainamount", "grain amount"],
        "Grain Size": ["grainsize", "grain size"],
        "Grain Roughness": ["grainroughness", "grain roughness"],
    },
    "HSL": {
        "Red Hue": ["redhue", "red hue"],
        "Red Saturation": ["redsaturation", "red saturation"],
        "Red Luminance": ["redluminance", "red luminance"],

        "Orange Hue": ["orangehue", "orange hue"],
        "Orange Saturation": ["orangesaturation", "orange saturation"],
        "Orange Luminance": ["oraluminance", "orange luminance"],

        "Yellow Hue": ["yellowhue", "yellow hue"],
        "Yellow Saturation": ["yellowsaturation", "yellow saturation"],
        "Yellow Luminance": ["yellowluminance", "yellow luminance"],

        "Green Hue": ["greenhue", "green hue"],
        "Green Saturation": ["greensaturation", "green saturation"],
        "Green Luminance": ["greenluminance", "green luminance"],

        "Cyan Hue": ["cyanhue", "cyan hue", "aquahue", "aqua hue"],
        "Cyan Saturation": ["cyansaturation", "cyan saturation", "aquasaturation", "aqua saturation"],
        "Cyan Luminance": ["cyanluminance", "cyan luminance", "aqualuminance", "aqua luminance"],

        "Blue Hue": ["bluehue", "blue hue"],
        "Blue Saturation": ["bluesaturation", "blue saturation"],
        "Blue Luminance": ["blueluminance", "blue luminance"],

        "Purple Hue": ["purplehue", "purple hue"],
        "Purple Saturation": ["purplesaturation", "purple saturation"],
        "Purple Luminance": ["purpleluminance", "purple luminance"],

        "Magenta Hue": ["magentahue", "magenta hue"],
        "Magenta Saturation": ["magentasaturation", "magenta saturation"],
        "Magenta Luminance": ["magentaluminance", "magenta luminance"],
    },
}

NUMERIC_RE = re.compile(r"[+-]?\d+(?:[.,]\d+)?")
NON_ALNUM_RE = re.compile(r"[^a-z0-9.+-]+", re.IGNORECASE)


# =========================================================
# Public API
# =========================================================

def extract_from_images(files: Iterable[Any]) -> Dict[str, Any]:
    """
    Accepts werkzeug FileStorage objects or similar file-like objects.
    Returns a DISPLAY-style preset payload:

    {
      "Light": {...},
      "Effects": {...},
      "HSL": {...},
      "Curves": {...},
      "meta": {...},
      "sources": [...]
    }
    """
    file_list = list(files or [])
    if not file_list:
        return _empty_payload()

    per_file_results = []
    for file_obj in file_list:
        try:
            image = _load_image(file_obj)
            result = _extract_from_single_image(image)
            result["source"] = getattr(file_obj, "filename", "unknown")
            per_file_results.append(result)
        except Exception as exc:
            per_file_results.append({
                "source": getattr(file_obj, "filename", "unknown"),
                "error": str(exc),
                "sections": deepcopy(DISPLAY_TEMPLATE),
            })

    merged = _merge_results(per_file_results)

    return {
        **merged,
        "sources": [item.get("source", "unknown") for item in per_file_results],
        "meta": {
            "parser": "ocr",
            "engine": "pytesseract",
            "items_processed": len(file_list),
        },
    }


# =========================================================
# Single-image extraction
# =========================================================

def _extract_from_single_image(image: Image.Image) -> Dict[str, Any]:
    """
    Returns:
    {
      "sections": { Light, Effects, HSL, Curves },
      "raw_texts": [ ... ],
      "best_text": "...",
    }
    """
    variants = _preprocess_variants(image)

    candidates = []
    for variant in variants:
        text = _ocr_text(variant)
        sections = _parse_text(text)
        score = _score_sections(sections)
        candidates.append({
            "text": text,
            "sections": sections,
            "score": score,
        })

    best = max(candidates, key=lambda item: item["score"])
    return {
        "sections": best["sections"],
        "raw_texts": [c["text"] for c in candidates],
        "best_text": best["text"],
    }


# =========================================================
# Image loading / preprocessing / OCR
# =========================================================

def _load_image(file_obj: Any) -> Image.Image:
    """
    Supports:
    - werkzeug FileStorage
    - file-like object with read()
    - raw bytes
    """
    if hasattr(file_obj, "read"):
        data = file_obj.read()
        try:
            file_obj.stream.seek(0)
        except Exception:
            pass
    elif isinstance(file_obj, (bytes, bytearray)):
        data = bytes(file_obj)
    else:
        raise TypeError(f"Unsupported file type: {type(file_obj)!r}")

    if not data:
        raise ValueError("Empty image data")

    return Image.open(io.BytesIO(data)).convert("RGB")


def _preprocess_variants(image: Image.Image) -> List[Image.Image]:
    """
    Build OCR-friendly variants.
    We try multiple versions because Lightroom screenshots can be light or dark,
    and OCR quality changes drastically by theme.
    """
    base = image.convert("RGB")

    # Variant 1: sharpen + grayscale + contrast boost
    v1 = ImageOps.grayscale(base)
    v1 = ImageEnhance.Contrast(v1).enhance(2.0)
    v1 = ImageEnhance.Sharpness(v1).enhance(2.0)
    v1 = v1.resize((v1.width * 2, v1.height * 2))
    v1 = v1.filter(ImageFilter.MedianFilter(size=3))

    # Variant 2: inverted grayscale for dark UI
    v2 = ImageOps.invert(ImageOps.grayscale(base))
    v2 = ImageEnhance.Contrast(v2).enhance(2.2)
    v2 = ImageEnhance.Sharpness(v2).enhance(2.0)
    v2 = v2.resize((v2.width * 2, v2.height * 2))
    v2 = v2.filter(ImageFilter.MedianFilter(size=3))

    # Variant 3: plain grayscale, slightly sharpened
    v3 = ImageOps.grayscale(base)
    v3 = ImageEnhance.Contrast(v3).enhance(1.6)
    v3 = ImageEnhance.Sharpness(v3).enhance(1.6)
    v3 = v3.resize((v3.width * 2, v3.height * 2))

    return [v1, v2, v3]


def _ocr_text(image: Image.Image) -> str:
    try:
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(image, config=config, lang="eng")
    except Exception as exc:
        raise RuntimeError(
            "OCR failed. Make sure Tesseract OCR is installed on the server."
        ) from exc

    return _normalize_text(text)


def _normalize_text(text: str) -> str:
    text = text.replace("\x0c", "\n")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    text = text.replace("•", " ")
    text = text.replace(":", " : ")
    text = text.replace("=", " = ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


# =========================================================
# Parsing
# =========================================================

def _parse_text(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse OCR text into Lightroom sections.
    """
    sections = deepcopy(DISPLAY_TEMPLATE)

    if not text:
        return sections

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    flat_text = " ".join(lines)
    flat_text_norm = _normalize_for_match(flat_text)

    # 1) Hard scan line-by-line for numeric fields.
    for section_name, mapping in FIELD_ALIASES.items():
        for display_key in mapping.keys():
            value = _find_value_in_lines(lines, mapping[display_key])
            if value is not None:
                sections[section_name][display_key] = value

    # 2) If OCR saw "curve", preserve the default curve label.
    #    We do not pretend to reconstruct curve points from text OCR.
    if "curve" in flat_text_norm or "curves" in flat_text_norm:
        # Keep the template values; these are display placeholders.
        pass

    return sections


def _find_value_in_lines(lines: List[str], aliases: List[str]) -> Optional[Any]:
    """
    Try to extract a number near an alias in OCR lines.
    """
    for line in lines:
        value = _extract_value_from_line(line, aliases)
        if value is not None:
            return value
    return None


def _extract_value_from_line(line: str, aliases: List[str]) -> Optional[Any]:
    """
    Match by normalized alias, then read the first number after it.
    Works for lines such as:
      Exposure 0.8
      Contrast: 0
      Highlights -45
      Red Saturation -40
    """
    if not line:
        return None

    line_norm = _normalize_for_match(line)

    for alias in aliases:
        alias_norm = _normalize_for_match(alias)
        idx = line_norm.find(alias_norm)
        if idx == -1:
            continue

        tail = line_norm[idx + len(alias_norm):]
        num = _first_number(tail)
        if num is not None:
            return num

        # fallback: read any number in the full line
        num = _first_number(line_norm)
        if num is not None:
            return num

    return None


def _normalize_for_match(text: str) -> str:
    text = text.lower().strip()
    text = text.replace(",", ".")
    text = NON_ALNUM_RE.sub("", text)
    return text


def _first_number(text: str) -> Optional[Any]:
    if not text:
        return None

    match = NUMERIC_RE.search(text.replace(",", "."))
    if not match:
        return None

    raw = match.group(0).replace(",", ".")
    try:
        value = float(raw)
        if value.is_integer():
            return int(value)
        return round(value, 2)
    except ValueError:
        return None


def _score_sections(sections: Dict[str, Dict[str, Any]]) -> int:
    """
    Simple heuristic: how many non-default numeric values were extracted.
    """
    score = 0

    for section_name in ("Light", "Effects", "HSL"):
        for key, value in sections.get(section_name, {}).items():
            if isinstance(value, (int, float)) and value != 0:
                score += 1

    return score


# =========================================================
# Merge across multiple images
# =========================================================

def _merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(DISPLAY_TEMPLATE)

    # Collect values per field
    field_values: Dict[Tuple[str, str], List[Any]] = defaultdict(list)

    for item in results:
        sections = item.get("sections") or {}
        for section_name, fields in sections.items():
            if section_name not in merged:
                continue
            for key, value in fields.items():
                if value is None:
                    continue
                if isinstance(value, str) and value.strip() == "":
                    continue
                field_values[(section_name, key)].append(value)

    # Majority vote / first valid
    for (section_name, key), values in field_values.items():
        merged[section_name][key] = _choose_best_value(values)

    return merged


def _choose_best_value(values: List[Any]) -> Any:
    if not values:
        return 0

    # Prefer exact numeric majority if possible.
    normalized = []
    for value in values:
        if isinstance(value, (int, float)):
            normalized.append(value)
        else:
            normalized.append(value)

    counter = Counter(normalized)
    best_value, _ = counter.most_common(1)[0]
    return best_value


# =========================================================
# Fallback
# =========================================================

def _empty_payload() -> Dict[str, Any]:
    return {
        **deepcopy(DISPLAY_TEMPLATE),
        "sources": [],
        "meta": {
            "parser": "ocr",
            "engine": "pytesseract",
            "items_processed": 0,
        },
    }
