import io
import re
from collections import defaultdict, Counter

from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

from lightroom_schema import DISPLAY_TEMPLATE


FIELD_MAP = {
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

    "Grain Amount": ["grainamount", "grain amount"],
    "Grain Size": ["grainsize", "grain size"],
    "Grain Roughness": ["grainroughness", "grain roughness"],

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


NUMBER_RE = re.compile(r'[-+]?\d+(?:\.\d+)?')


def normalize(text):
    text = text.lower()
    text = text.replace(" ", "")
    text = text.replace(":", "")
    text = text.replace("—", "-")
    text = text.replace("–", "-")
    return text


def preprocess(img):

    variants = []

    gray = ImageOps.grayscale(img)
    gray = ImageEnhance.Contrast(gray).enhance(2)
    gray = ImageEnhance.Sharpness(gray).enhance(2)

    variants.append(gray)

    inv = ImageOps.invert(gray)
    variants.append(inv)

    blur = gray.filter(ImageFilter.MedianFilter(size=3))
    variants.append(blur)

    final = []

    for v in variants:
        v = v.resize((v.width * 2, v.height * 2))
        final.append(v)

    return final


def extract_number(text):

    match = NUMBER_RE.search(text)

    if not match:
        return None

    value = match.group()

    try:
        if "." in value:
            return float(value)
        return int(value)
    except:
        return None


def parse_text(text):

    result = defaultdict(dict)

    lines = text.splitlines()

    for raw_line in lines:

        line = normalize(raw_line)

        for field, aliases in FIELD_MAP.items():

            for alias in aliases:

                if alias in line:

                    value = extract_number(line)

                    if value is not None:

                        if field in [
                            "Exposure"
                        ]:
                            result["Light"][field] = value

                        elif field in [
                            "Contrast",
                            "Highlights",
                            "Shadows",
                            "Whites",
                            "Blacks"
                        ]:
                            result["Light"][field] = value

                        elif field in [
                            "Texture",
                            "Clarity",
                            "Dehaze",
                            "Vibrance",
                            "Saturation",
                            "Grain Amount",
                            "Grain Size",
                            "Grain Roughness"
                        ]:
                            result["Effects"][field] = value

                        else:
                            result["HSL"][field] = value

    return result


def merge_results(results):

    merged = defaultdict(dict)

    temp = defaultdict(list)

    for result in results:

        for section, values in result.items():

            for key, value in values.items():

                temp[(section, key)].append(value)

    for (section, key), values in temp.items():

        common = Counter(values).most_common(1)[0][0]

        merged[section][key] = common

    return merged


def fill_defaults(data):

    final = DISPLAY_TEMPLATE.copy()

    for section, values in data.items():

        if section not in final:
            final[section] = {}

        for key, value in values.items():
            final[section][key] = value

    return final


def extract_from_images(files):

    parsed_results = []

    for file in files:

        if hasattr(file, "read"):
            image = Image.open(file.stream).convert("RGB")
        else:
            image = Image.open(io.BytesIO(file)).convert("RGB")

        variants = preprocess(image)

        best = defaultdict(dict)

        best_score = 0

        for variant in variants:

            text = pytesseract.image_to_string(
                variant,
                config='--oem 3 --psm 6'
            )

            parsed = parse_text(text)

            score = sum(
                len(v)
                for v in parsed.values()
            )

            if score > best_score:
                best = parsed
                best_score = score

        parsed_results.append(best)

    merged = merge_results(parsed_results)

    final = fill_defaults(merged)

    return {
        **final,
        "meta": {
            "success": True
        }
    }
    
