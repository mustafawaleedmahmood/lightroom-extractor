from xml.sax.saxutils import escape

CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"


def _format_value(value):
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def _curve_point_to_text(point):
    if isinstance(point, (list, tuple)):
        return ",".join(str(item) for item in point)
    return str(point)


def build_xmp(normalized_preset):
    meta = normalized_preset.get("meta", {})
    settings = normalized_preset.get("settings", {})
    curves = normalized_preset.get("curves", {})

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="OpenAI Lightroom XMP Builder">',
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '    <rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"',
    ]

    base_attrs = {
        "ProcessVersion": meta.get("ProcessVersion", "11.0"),
        "ConvertToGrayscale": meta.get("ConvertToGrayscale", "False"),
        "CameraProfile": meta.get("CameraProfile", "Adobe Standard"),
        "Name": meta.get("Name", "Extracted Lightroom Preset"),
        "PresetType": "Normal",
        "Cluster": "User Presets",
    }

    for key, value in base_attrs.items():
        lines.append(f'      crs:{key}="{escape(_format_value(value))}"')

    settings_order = [
        "Exposure2012",
        "Contrast2012",
        "Highlights2012",
        "Shadows2012",
        "Whites2012",
        "Blacks2012",
        "Clarity2012",
        "Dehaze",
        "Texture",
        "Vibrance",
        "Saturation",
        "GrainAmount",
        "GrainSize",
        "GrainRoughness",
        "HueAdjustmentRed",
        "SaturationAdjustmentRed",
        "LuminanceAdjustmentRed",
        "HueAdjustmentOrange",
        "SaturationAdjustmentOrange",
        "LuminanceAdjustmentOrange",
        "HueAdjustmentYellow",
        "SaturationAdjustmentYellow",
        "LuminanceAdjustmentYellow",
        "HueAdjustmentGreen",
        "SaturationAdjustmentGreen",
        "LuminanceAdjustmentGreen",
        "HueAdjustmentAqua",
        "SaturationAdjustmentAqua",
        "LuminanceAdjustmentAqua",
        "HueAdjustmentBlue",
        "SaturationAdjustmentBlue",
        "LuminanceAdjustmentBlue",
        "HueAdjustmentPurple",
        "SaturationAdjustmentPurple",
        "LuminanceAdjustmentPurple",
        "HueAdjustmentMagenta",
        "SaturationAdjustmentMagenta",
        "LuminanceAdjustmentMagenta",
    ]

    for key in settings_order:
        if key in settings:
            lines.append(f'      crs:{key}="{escape(_format_value(settings[key]))}"')

    curve_order = [
        "ToneCurvePV2012",
        "ToneCurvePV2012Red",
        "ToneCurvePV2012Green",
        "ToneCurvePV2012Blue",
    ]

    if not curves:
        lines[-1] += " />"
    else:
        lines[-1] += ">"
        for key in curve_order:
            curve_points = curves.get(key)
            if not curve_points:
                continue

            lines.append(f"      <crs:{key}>")
            lines.append("        <rdf:Seq>")
            for point in curve_points:
                lines.append(f"          <rdf:li>{escape(_curve_point_to_text(point))}</rdf:li>")
            lines.append("        </rdf:Seq>")
            lines.append(f"      </crs:{key}>")

        lines.append("    </rdf:Description>")

    lines.append("  </rdf:RDF>")
    lines.append("</x:xmpmeta>")

    return "\n".join(lines)
