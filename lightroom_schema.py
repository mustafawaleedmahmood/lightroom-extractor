from copy import deepcopy

DISPLAY_TEMPLATE = {
    "Light": {
        "Exposure": 0,
        "Contrast": 0,
        "Highlights": 0,
        "Shadows": 0,
        "Whites": 0,
        "Blacks": 0,
    },
    "Effects": {
        "Clarity": 0,
        "Dehaze": 0,
        "Texture": 0,
        "Vibrance": 0,
        "Saturation": 0,
        "Grain Amount": 0,
        "Grain Size": 0,
        "Grain Roughness": 0,
    },
    "HSL": {
        "Red Hue": 0,
        "Red Saturation": 0,
        "Red Luminance": 0,
        "Orange Hue": 0,
        "Orange Saturation": 0,
        "Orange Luminance": 0,
        "Yellow Hue": 0,
        "Yellow Saturation": 0,
        "Yellow Luminance": 0,
        "Green Hue": 0,
        "Green Saturation": 0,
        "Green Luminance": 0,
        "Cyan Hue": 0,
        "Cyan Saturation": 0,
        "Cyan Luminance": 0,
        "Blue Hue": 0,
        "Blue Saturation": 0,
        "Blue Luminance": 0,
        "Purple Hue": 0,
        "Purple Saturation": 0,
        "Purple Luminance": 0,
        "Magenta Hue": 0,
        "Magenta Saturation": 0,
        "Magenta Luminance": 0,
    },
    "Curves": {
        "RGB": "منحنى مخصص",
        "Red": "منحنى مخصص",
        "Green": "منحنى مخصص",
        "Blue": "منحنى مخصص",
    },
}

LIGHT_MAP = {
    "Exposure": "Exposure2012",
    "Contrast": "Contrast2012",
    "Highlights": "Highlights2012",
    "Shadows": "Shadows2012",
    "Whites": "Whites2012",
    "Blacks": "Blacks2012",
}

EFFECTS_MAP = {
    "Clarity": "Clarity2012",
    "Dehaze": "Dehaze",
    "Texture": "Texture",
    "Vibrance": "Vibrance",
    "Saturation": "Saturation",
    "Grain Amount": "GrainAmount",
    "Grain Size": "GrainSize",
    "Grain Roughness": "GrainRoughness",
}

HSL_MAP = {
    "Red Hue": "HueAdjustmentRed",
    "Red Saturation": "SaturationAdjustmentRed",
    "Red Luminance": "LuminanceAdjustmentRed",
    "Orange Hue": "HueAdjustmentOrange",
    "Orange Saturation": "SaturationAdjustmentOrange",
    "Orange Luminance": "LuminanceAdjustmentOrange",
    "Yellow Hue": "HueAdjustmentYellow",
    "Yellow Saturation": "SaturationAdjustmentYellow",
    "Yellow Luminance": "LuminanceAdjustmentYellow",
    "Green Hue": "HueAdjustmentGreen",
    "Green Saturation": "SaturationAdjustmentGreen",
    "Green Luminance": "LuminanceAdjustmentGreen",
    "Cyan Hue": "HueAdjustmentAqua",
    "Cyan Saturation": "SaturationAdjustmentAqua",
    "Cyan Luminance": "LuminanceAdjustmentAqua",
    "Aqua Hue": "HueAdjustmentAqua",
    "Aqua Saturation": "SaturationAdjustmentAqua",
    "Aqua Luminance": "LuminanceAdjustmentAqua",
    "Blue Hue": "HueAdjustmentBlue",
    "Blue Saturation": "SaturationAdjustmentBlue",
    "Blue Luminance": "LuminanceAdjustmentBlue",
    "Purple Hue": "HueAdjustmentPurple",
    "Purple Saturation": "SaturationAdjustmentPurple",
    "Purple Luminance": "LuminanceAdjustmentPurple",
    "Magenta Hue": "HueAdjustmentMagenta",
    "Magenta Saturation": "SaturationAdjustmentMagenta",
    "Magenta Luminance": "LuminanceAdjustmentMagenta",
}

CURVE_MAP = {
    "RGB": "ToneCurvePV2012",
    "Red": "ToneCurvePV2012Red",
    "Green": "ToneCurvePV2012Green",
    "Blue": "ToneCurvePV2012Blue",
}

DEFAULT_META = {
    "ProcessVersion": "11.0",
    "ConvertToGrayscale": "False",
    "CameraProfile": "Adobe Standard",
    "Name": "Extracted Lightroom Preset",
}


def _clone_display_template():
    return deepcopy(DISPLAY_TEMPLATE)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_number(value):
    if _is_number(value):
        return value

    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return value

    return value


def _copy_section(source, mapping):
    result = {}
    if not isinstance(source, dict):
        return result

    for display_key, xmp_key in mapping.items():
        if display_key in source:
            value = source[display_key]
            coerced = _coerce_number(value)
            if coerced is not None:
                result[xmp_key] = coerced

    return result


def _normalize_curves(source):
    curves = {}
    if not isinstance(source, dict):
        return curves

    for display_key, xmp_key in CURVE_MAP.items():
        value = source.get(display_key)
        if isinstance(value, (list, tuple)) and value:
            curves[xmp_key] = [str(item) for item in value]
        elif isinstance(value, dict) and value:
            points = value.get("points")
            if isinstance(points, (list, tuple)) and points:
                curves[xmp_key] = [str(item) for item in points]

    return curves


def normalize_preset_payload(payload):
    """
    Returns:
    {
        "display": {...},   # for UI
        "canonical": {
            "meta": {...},
            "settings": {...},  # real CRS keys
            "curves": {...}     # real CRS curve keys
        }
    }
    """
    display = _clone_display_template()

    if not isinstance(payload, dict):
        return {
            "display": display,
            "canonical": {
                "meta": deepcopy(DEFAULT_META),
                "settings": {},
                "curves": {},
            },
        }

    # Allow both wrapper styles and direct payloads.
    source = payload.get("presetData") if isinstance(payload.get("presetData"), dict) else payload
    if not isinstance(source, dict):
        source = payload

    light = source.get("Light", {})
    effects = source.get("Effects", {})
    hsl = source.get("HSL", {})
    curves = source.get("Curves", {})

    if isinstance(light, dict):
        for key, value in light.items():
            if key in display["Light"]:
                display["Light"][key] = value

    if isinstance(effects, dict):
        for key, value in effects.items():
            if key in display["Effects"]:
                display["Effects"][key] = value

    if isinstance(hsl, dict):
        for key, value in hsl.items():
            if key in display["HSL"]:
                display["HSL"][key] = value

    if isinstance(curves, dict):
        for key, value in curves.items():
            if key in display["Curves"]:
                display["Curves"][key] = value

    canonical_settings = {}
    canonical_settings.update(_copy_section(display["Light"], LIGHT_MAP))
    canonical_settings.update(_copy_section(display["Effects"], EFFECTS_MAP))
    canonical_settings.update(_copy_section(display["HSL"], HSL_MAP))

    canonical_curves = _normalize_curves(display["Curves"])

    meta = deepcopy(DEFAULT_META)
    meta_source = source.get("meta") if isinstance(source.get("meta"), dict) else {}
    if isinstance(meta_source, dict):
        for key in meta:
            if key in meta_source and meta_source[key] not in (None, ""):
                meta[key] = str(meta_source[key])

    return {
        "display": display,
        "canonical": {
            "meta": meta,
            "settings": canonical_settings,
            "curves": canonical_curves,
        },
    }
