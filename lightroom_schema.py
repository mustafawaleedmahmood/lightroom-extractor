from copy import deepcopy
from uuid import uuid4


X_NS = "adobe:ns:meta/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"


SECTION_FIELDS = {
    "Light": {
        "Exposure": ("Exposure2012", 0.0),
        "Contrast": ("Contrast2012", 0),
        "Highlights": ("Highlights2012", 0),
        "Shadows": ("Shadows2012", 0),
        "Whites": ("Whites2012", 0),
        "Blacks": ("Blacks2012", 0),
    },
    "Effects": {
        "Texture": ("Texture", 0),
        "Clarity": ("Clarity2012", 0),
        "Dehaze": ("Dehaze", 0),
        "Vibrance": ("Vibrance", 0),
        "Saturation": ("Saturation", 0),
        "Grain Amount": ("GrainAmount", 0),
        "Grain Size": ("GrainSize", 25),
        "Grain Roughness": ("GrainFrequency", 50),
    },
    "HSL": {
        "Red Hue": ("HueAdjustmentRed", 0),
        "Red Saturation": ("SaturationAdjustmentRed", 0),
        "Red Luminance": ("LuminanceAdjustmentRed", 0),
        "Orange Hue": ("HueAdjustmentOrange", 0),
        "Orange Saturation": ("SaturationAdjustmentOrange", 0),
        "Orange Luminance": ("LuminanceAdjustmentOrange", 0),
        "Yellow Hue": ("HueAdjustmentYellow", 0),
        "Yellow Saturation": ("SaturationAdjustmentYellow", 0),
        "Yellow Luminance": ("LuminanceAdjustmentYellow", 0),
        "Green Hue": ("HueAdjustmentGreen", 0),
        "Green Saturation": ("SaturationAdjustmentGreen", 0),
        "Green Luminance": ("LuminanceAdjustmentGreen", 0),
        "Cyan Hue": ("HueAdjustmentAqua", 0),
        "Cyan Saturation": ("SaturationAdjustmentAqua", 0),
        "Cyan Luminance": ("LuminanceAdjustmentAqua", 0),
        "Blue Hue": ("HueAdjustmentBlue", 0),
        "Blue Saturation": ("SaturationAdjustmentBlue", 0),
        "Blue Luminance": ("LuminanceAdjustmentBlue", 0),
        "Purple Hue": ("HueAdjustmentPurple", 0),
        "Purple Saturation": ("SaturationAdjustmentPurple", 0),
        "Purple Luminance": ("LuminanceAdjustmentPurple", 0),
        "Magenta Hue": ("HueAdjustmentMagenta", 0),
        "Magenta Saturation": ("SaturationAdjustmentMagenta", 0),
        "Magenta Luminance": ("LuminanceAdjustmentMagenta", 0),
    },
}


CURVE_MAP = {
    "RGB": "ToneCurvePV2012",
    "Red": "ToneCurvePV2012Red",
    "Green": "ToneCurvePV2012Green",
    "Blue": "ToneCurvePV2012Blue",
}


DEFAULT_CURVES = {
    "ToneCurvePV2012": ["0, 0", "255, 255"],
    "ToneCurvePV2012Red": ["0, 0", "255, 255"],
    "ToneCurvePV2012Green": ["0, 0", "255, 255"],
    "ToneCurvePV2012Blue": ["0, 0", "255, 255"],
}


DISPLAY_TEMPLATE = {
    section: {
        display_key: default
        for display_key, (_, default) in fields.items()
    }
    for section, fields in SECTION_FIELDS.items()
}
DISPLAY_TEMPLATE["Curves"] = {
    "RGB": DEFAULT_CURVES["ToneCurvePV2012"][:],
    "Red": DEFAULT_CURVES["ToneCurvePV2012Red"][:],
    "Green": DEFAULT_CURVES["ToneCurvePV2012Green"][:],
    "Blue": DEFAULT_CURVES["ToneCurvePV2012Blue"][:],
}


DISPLAY_TO_CRS = {
    display_key: crs_key
    for fields in SECTION_FIELDS.values()
    for display_key, (crs_key, _) in fields.items()
}
CRS_TO_DISPLAY = {crs_key: display_key for display_key, crs_key in DISPLAY_TO_CRS.items()}
CRS_TO_DISPLAY.update({
    "HueAdjustmentAqua": "Cyan Hue",
    "SaturationAdjustmentAqua": "Cyan Saturation",
    "LuminanceAdjustmentAqua": "Cyan Luminance",
})


DEFAULT_META = {
    "PresetType": "Normal",
    "Cluster": "",
    "UUID": "",
    "SupportsAmount": "False",
    "SupportsColor": "True",
    "SupportsMonochrome": "True",
    "SupportsHighDynamicRange": "True",
    "SupportsNormalDynamicRange": "True",
    "SupportsSceneReferred": "True",
    "SupportsOutputReferred": "True",
    "CameraModelRestriction": "",
    "Copyright": "",
    "ContactInfo": "",
    "Version": "11.3",
    "ProcessVersion": "11.0",
    "Name": "Extracted Lightroom Preset",
    "ShortName": "",
    "SortName": "",
    "Group": "User Presets",
    "Description": "",
}


DEFAULT_SETTINGS = {
    "WhiteBalance": "As Shot",
    "IncrementalTemperature": 0,
    "IncrementalTint": 0,
    "Saturation": 0,
    "Sharpness": 0,
    "LuminanceSmoothing": 0,
    "ColorNoiseReduction": 0,
    "ShadowTint": 0,
    "RedHue": 0,
    "RedSaturation": 0,
    "GreenHue": 0,
    "GreenSaturation": 0,
    "BlueHue": 0,
    "BlueSaturation": 0,
    "Vibrance": 0,
    "HueAdjustmentRed": 0,
    "HueAdjustmentOrange": 0,
    "HueAdjustmentYellow": 0,
    "HueAdjustmentGreen": 0,
    "HueAdjustmentAqua": 0,
    "HueAdjustmentBlue": 0,
    "HueAdjustmentPurple": 0,
    "HueAdjustmentMagenta": 0,
    "SaturationAdjustmentRed": 0,
    "SaturationAdjustmentOrange": 0,
    "SaturationAdjustmentYellow": 0,
    "SaturationAdjustmentGreen": 0,
    "SaturationAdjustmentAqua": 0,
    "SaturationAdjustmentBlue": 0,
    "SaturationAdjustmentPurple": 0,
    "SaturationAdjustmentMagenta": 0,
    "LuminanceAdjustmentRed": 0,
    "LuminanceAdjustmentOrange": 0,
    "LuminanceAdjustmentYellow": 0,
    "LuminanceAdjustmentGreen": 0,
    "LuminanceAdjustmentAqua": 0,
    "LuminanceAdjustmentBlue": 0,
    "LuminanceAdjustmentPurple": 0,
    "LuminanceAdjustmentMagenta": 0,
    "SplitToningShadowHue": 0,
    "SplitToningShadowSaturation": 0,
    "SplitToningHighlightHue": 0,
    "SplitToningHighlightSaturation": 0,
    "SplitToningBalance": 0,
    "ParametricShadows": 0,
    "ParametricDarks": 0,
    "ParametricLights": 0,
    "ParametricHighlights": 0,
    "ParametricShadowSplit": 25,
    "ParametricMidtoneSplit": 50,
    "ParametricHighlightSplit": 75,
    "SharpenRadius": "+1.0",
    "SharpenDetail": 25,
    "SharpenEdgeMasking": 0,
    "PostCropVignetteAmount": 0,
    "GrainAmount": 0,
    "GrainSize": 25,
    "GrainFrequency": 50,
    "LensProfileEnable": 0,
    "LensManualDistortionAmount": 0,
    "PerspectiveVertical": 0,
    "PerspectiveHorizontal": 0,
    "PerspectiveRotate": "0.0",
    "PerspectiveScale": 100,
    "PerspectiveAspect": 0,
    "PerspectiveUpright": 0,
    "PerspectiveX": "0.00",
    "PerspectiveY": "0.00",
    "AutoLateralCA": 0,
    "Exposure2012": "0.00",
    "Contrast2012": 0,
    "Highlights2012": 0,
    "Shadows2012": 0,
    "Whites2012": 0,
    "Blacks2012": 0,
    "Clarity2012": 0,
    "DefringePurpleAmount": 0,
    "DefringePurpleHueLo": 30,
    "DefringePurpleHueHi": 70,
    "DefringeGreenAmount": 0,
    "DefringeGreenHueLo": 40,
    "DefringeGreenHueHi": 60,
    "Dehaze": 0,
    "Texture": 0,
    "ConvertToGrayscale": "False",
    "OverrideLookVignette": "False",
    "ToneCurveName2012": "Linear",
    "CameraProfile": "Adobe Standard",
    "LensProfileSetup": "LensDefaults",
}


def _clone_display_template():
    return deepcopy(DISPLAY_TEMPLATE)


def _strip_crs_prefix(key):
    if not isinstance(key, str):
        return key
    return key[4:] if key.startswith("crs:") else key


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_number(value):
    if _is_number(value):
        return value

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        text = (
            text.replace("\u2212", "-")
            .replace("\u2013", "-")
            .replace("\u2014", "-")
            .replace("+ ", "+")
            .replace("- ", "-")
        )
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        try:
            number = float(text)
            return int(number) if number.is_integer() and "." not in text else number
        except ValueError:
            return value

    return value


def _normalize_curve_points(points):
    normalized = []
    if not isinstance(points, (list, tuple)):
        return normalized

    for point in points:
        if isinstance(point, str):
            text = point.strip()
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            text = f"{int(round(float(point[0])))}, {int(round(float(point[1])))}"
        elif isinstance(point, dict) and {"x", "y"} <= set(point):
            text = f"{int(round(float(point['x'])))}, {int(round(float(point['y'])))}"
        else:
            continue

        if "," in text:
            left, right = text.split(",", 1)
            try:
                x = max(0, min(255, int(round(float(left.strip())))))
                y = max(0, min(255, int(round(float(right.strip())))))
            except ValueError:
                continue
            normalized.append(f"{x}, {y}")

    if not normalized:
        return []

    points_by_x = {}
    for point in normalized:
        x_text, y_text = point.split(",", 1)
        points_by_x[int(x_text.strip())] = int(y_text.strip())

    ordered = [f"{x}, {points_by_x[x]}" for x in sorted(points_by_x)]
    if not ordered or not ordered[0].startswith("0,"):
        ordered.insert(0, "0, 0")
    if not ordered[-1].startswith("255,"):
        ordered.append("255, 255")
    return ordered


def _copy_display_section(source, display, section_name, detected_fields):
    values = source.get(section_name)
    if not isinstance(values, dict):
        return
    for display_key in display.get(section_name, {}):
        if display_key in values:
            coerced = _coerce_number(values[display_key])
            if coerced is not None:
                display[section_name][display_key] = coerced
                detected_fields.add(display_key)


def _apply_raw_crs_settings(source, display, detected_fields):
    if not isinstance(source, dict):
        return

    raw_settings = source.get("settings") if isinstance(source.get("settings"), dict) else source
    for raw_key, value in raw_settings.items():
        key = _strip_crs_prefix(raw_key)
        display_key = CRS_TO_DISPLAY.get(key)
        if display_key:
            section = next(
                section_name
                for section_name, fields in SECTION_FIELDS.items()
                if display_key in fields
            )
            coerced = _coerce_number(value)
            if coerced is not None:
                display[section][display_key] = coerced
                detected_fields.add(display_key)


def _normalize_curves(source, warnings):
    curves = deepcopy(DEFAULT_CURVES)
    if not isinstance(source, dict):
        return curves

    raw_curves = source.get("curves") if isinstance(source.get("curves"), dict) else source
    display_curves = source.get("Curves") if isinstance(source.get("Curves"), dict) else {}

    for display_key, crs_key in CURVE_MAP.items():
        value = display_curves.get(display_key)
        if isinstance(value, dict):
            value = value.get("points")
        points = _normalize_curve_points(value)
        if points:
            curves[crs_key] = points
        elif value not in (None, "", "custom", "Custom"):
            warnings.append(f"Curve {display_key} was present but did not contain usable points.")

    for raw_key, value in raw_curves.items():
        crs_key = _strip_crs_prefix(raw_key)
        if crs_key in DEFAULT_CURVES:
            points = _normalize_curve_points(value)
            if points:
                curves[crs_key] = points

    return curves


def _canonical_settings_from_display(display):
    settings = deepcopy(DEFAULT_SETTINGS)
    for section_name, fields in SECTION_FIELDS.items():
        for display_key, (crs_key, _) in fields.items():
            value = _coerce_number(display[section_name][display_key])
            if value is not None:
                settings[crs_key] = value
    return settings


def normalize_preset_payload(payload):
    """
    Normalizes any accepted input shape into one stable internal contract.

    Returns:
    {
        "display": {"Light": ..., "Effects": ..., "HSL": ..., "Curves": ...},
        "canonical": {"meta": {...}, "settings": {...}, "curves": {...}},
        "detected_fields": [...],
        "warnings": [...]
    }
    """
    display = _clone_display_template()
    warnings = []
    detected_fields = set()

    if not isinstance(payload, dict):
        payload = {}

    source = payload.get("canonical") if isinstance(payload.get("canonical"), dict) else payload
    source = source.get("presetData") if isinstance(source.get("presetData"), dict) else source

    for section_name in SECTION_FIELDS:
        _copy_display_section(source, display, section_name, detected_fields)

    _apply_raw_crs_settings(source, display, detected_fields)

    settings = _canonical_settings_from_display(display)
    if isinstance(source.get("settings"), dict):
        for raw_key, value in source["settings"].items():
            key = _strip_crs_prefix(raw_key)
            if key in DEFAULT_SETTINGS:
                coerced = _coerce_number(value)
                if coerced is not None:
                    settings[key] = coerced

    curves = _normalize_curves(source, warnings)
    display["Curves"] = {
        "RGB": curves["ToneCurvePV2012"][:],
        "Red": curves["ToneCurvePV2012Red"][:],
        "Green": curves["ToneCurvePV2012Green"][:],
        "Blue": curves["ToneCurvePV2012Blue"][:],
    }

    meta = deepcopy(DEFAULT_META)
    meta["UUID"] = uuid4().hex.upper()
    meta_source = source.get("meta") if isinstance(source.get("meta"), dict) else {}
    for key in meta:
        if key in meta_source and meta_source[key] not in (None, ""):
            meta[key] = str(meta_source[key])

    return {
        "display": display,
        "canonical": {
            "meta": meta,
            "settings": settings,
            "curves": curves,
        },
        "detected_fields": sorted(detected_fields),
        "warnings": warnings,
    }
