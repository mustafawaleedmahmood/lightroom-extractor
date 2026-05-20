from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString


# =========================================================
# Lightroom XMP Mapping
# =========================================================

LIGHTROOM_FIELD_MAP = {
    # Light
    "Exposure": "crs:Exposure2012",
    "Contrast": "crs:Contrast2012",
    "Highlights": "crs:Highlights2012",
    "Shadows": "crs:Shadows2012",
    "Whites": "crs:Whites2012",
    "Blacks": "crs:Blacks2012",

    # Effects
    "Texture": "crs:Texture",
    "Clarity": "crs:Clarity2012",
    "Dehaze": "crs:Dehaze",
    "Vibrance": "crs:Vibrance",
    "Saturation": "crs:Saturation",

    "Grain Amount": "crs:GrainAmount",
    "Grain Size": "crs:GrainSize",
    "Grain Roughness": "crs:GrainFrequency",

    # HSL
    "Red Hue": "crs:HueAdjustmentRed",
    "Red Saturation": "crs:SaturationAdjustmentRed",
    "Red Luminance": "crs:LuminanceAdjustmentRed",

    "Orange Hue": "crs:HueAdjustmentOrange",
    "Orange Saturation": "crs:SaturationAdjustmentOrange",
    "Orange Luminance": "crs:LuminanceAdjustmentOrange",

    "Yellow Hue": "crs:HueAdjustmentYellow",
    "Yellow Saturation": "crs:SaturationAdjustmentYellow",
    "Yellow Luminance": "crs:LuminanceAdjustmentYellow",

    "Green Hue": "crs:HueAdjustmentGreen",
    "Green Saturation": "crs:SaturationAdjustmentGreen",
    "Green Luminance": "crs:LuminanceAdjustmentGreen",

    "Cyan Hue": "crs:HueAdjustmentAqua",
    "Cyan Saturation": "crs:SaturationAdjustmentAqua",
    "Cyan Luminance": "crs:LuminanceAdjustmentAqua",

    "Blue Hue": "crs:HueAdjustmentBlue",
    "Blue Saturation": "crs:SaturationAdjustmentBlue",
    "Blue Luminance": "crs:LuminanceAdjustmentBlue",

    "Purple Hue": "crs:HueAdjustmentPurple",
    "Purple Saturation": "crs:SaturationAdjustmentPurple",
    "Purple Luminance": "crs:LuminanceAdjustmentPurple",

    "Magenta Hue": "crs:HueAdjustmentMagenta",
    "Magenta Saturation": "crs:SaturationAdjustmentMagenta",
    "Magenta Luminance": "crs:LuminanceAdjustmentMagenta",
}


# =========================================================
# Helpers
# =========================================================

def format_value(value):
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


# =========================================================
# Build XMP
# =========================================================

def build_xmp(settings):

    xmpmeta = Element(
        "x:xmpmeta",
        {
            "xmlns:x": "adobe:ns:meta/",
            "x:xmptk": "Adobe XMP Core"
        }
    )

    rdf = SubElement(
        xmpmeta,
        "rdf:RDF",
        {
            "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        }
    )

    description = SubElement(
        rdf,
        "rdf:Description",
        {
            "rdf:about": "",
            "xmlns:crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
            "crs:Version": "15.0",
            "crs:ProcessVersion": "11.0",
        }
    )

    # =====================================================
    # Light
    # =====================================================

    for key, value in settings.get("Light", {}).items():
        if key in LIGHTROOM_FIELD_MAP:
            description.set(
                LIGHTROOM_FIELD_MAP[key],
                format_value(value)
            )

    # =====================================================
    # Effects
    # =====================================================

    for key, value in settings.get("Effects", {}).items():
        if key in LIGHTROOM_FIELD_MAP:
            description.set(
                LIGHTROOM_FIELD_MAP[key],
                format_value(value)
            )

    # =====================================================
    # HSL
    # =====================================================

    for key, value in settings.get("HSL", {}).items():
        if key in LIGHTROOM_FIELD_MAP:
            description.set(
                LIGHTROOM_FIELD_MAP[key],
                format_value(value)
            )

    # =====================================================
    # Default Lightroom Flags
    # =====================================================

    description.set("crs:HasSettings", "True")
    description.set("crs:HasCrop", "False")
    description.set("crs:AlreadyApplied", "False")

    # =====================================================
    # Curves
    # =====================================================

    tone_curve = settings.get("Curves", {}).get("RGB")

    if tone_curve and isinstance(tone_curve, list):

        curve_seq = SubElement(
            description,
            "crs:ToneCurvePV2012"
        )

        seq = SubElement(
            curve_seq,
            "rdf:Seq"
        )

        for point in tone_curve:
            li = SubElement(seq, "rdf:li")
            li.text = point

    # =====================================================
    # Pretty XML
    # =====================================================

    xml_bytes = tostring(
        xmpmeta,
        encoding="utf-8"
    )

    parsed = parseString(xml_bytes)

    return parsed.toprettyxml(indent="  ")
