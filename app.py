import json
import os
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from lightroom_schema import normalize_preset_payload
from xmp_builder import build_xmp
from xmp_validator import validate_xmp_content

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)


@app.get("/")
def home():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return send_file(index_path)
    return jsonify({
        "success": False,
        "error": "index.html not found"
    }), 404


@app.get("/api/health")
def health():
    return jsonify({
        "success": True,
        "status": "healthy"
    }), 200


def _read_payload():
    """
    Accepts:
    1) application/json
    2) multipart/form-data with presetData field
    """
    payload = request.get_json(silent=True)
    if isinstance(payload, dict) and payload:
        return payload

    raw = request.form.get("presetData")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


@app.post("/api/process")
def process():
    payload = _read_payload()

    if not payload:
        return jsonify({
            "success": False,
            "error": (
                "No presetData payload received. "
                "Send the extracted Lightroom data from the frontend."
            )
        }), 400

    normalized = normalize_preset_payload(payload)
    xmp_text = build_xmp(normalized)
    validation = validate_xmp_content(xmp_text, normalized)

    if not validation["success"]:
        return jsonify({
            "success": False,
            "error": validation["error"]
        }), 500

    return jsonify({
        "success": True,
        "message": "XMP generated successfully",
        "settings": normalized["display"],
        "canonical": normalized["canonical"],
        "xmp": xmp_text,
        "validation": validation
    }), 200


@app.get("/api/stats")
def stats():
    return jsonify({
        "success": True,
        "stats": {
            "sections": 4,
            "supports_json_payload": True,
            "supports_form_payload": True
        }
    }), 200


@app.errorhandler(404)
def not_found(_):
    return jsonify({
        "success": False,
        "error": "Resource not found"
    }), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
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
    def validate_xmp_content(xmp_text, normalized_preset):
    settings = normalized_preset.get("settings", {})
    curves = normalized_preset.get("curves", {})

    if not isinstance(xmp_text, str) or not xmp_text.strip():
        return {
            "success": False,
            "error": "Generated XMP is empty"
        }

    missing_settings = []
    for key in settings.keys():
        if f'crs:{key}="' not in xmp_text:
            missing_settings.append(key)

    missing_curves = []
    for key, points in curves.items():
        if not points:
            continue
        if f"<crs:{key}>" not in xmp_text:
            missing_curves.append(key)

    if missing_settings or missing_curves:
        parts = []
        if missing_settings:
            parts.append(f"missing settings: {', '.join(missing_settings)}")
        if missing_curves:
            parts.append(f"missing curves: {', '.join(missing_curves)}")
        return {
            "success": False,
            "error": "XMP validation failed: " + " | ".join(parts)
        }

    return {
        "success": True
    }
