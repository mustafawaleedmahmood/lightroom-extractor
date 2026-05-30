from xml.etree import ElementTree as ET

from lightroom_schema import CRS_NS, DEFAULT_CURVES, RDF_NS, normalize_preset_payload
from xmp_builder import format_value


def _crs_attr(name):
    return f"{{{CRS_NS}}}{name}"


def _find_description(root):
    return root.find(f".//{{{RDF_NS}}}Description")


def _curve_points(description, curve_name):
    curve = description.find(f"{{{CRS_NS}}}{curve_name}")
    if curve is None:
        return []
    return [
        (li.text or "").strip()
        for li in curve.findall(f".//{{{RDF_NS}}}li")
    ]


def validate_xmp_content(xmp_text, normalized_preset):
    if not isinstance(xmp_text, str) or not xmp_text.strip():
        return {"success": False, "error": "Generated XMP is empty"}

    try:
        root = ET.fromstring(xmp_text.encode("utf-8"))
    except ET.ParseError as exc:
        return {"success": False, "error": f"Generated XMP is not valid XML: {exc}"}

    description = _find_description(root)
    if description is None:
        return {"success": False, "error": "Generated XMP does not contain rdf:Description"}

    canonical = normalize_preset_payload(normalized_preset).get("canonical", {})
    settings = canonical.get("settings", {})
    curves = {**DEFAULT_CURVES, **canonical.get("curves", {})}

    missing_settings = []
    mismatched_settings = []
    for key, value in settings.items():
        actual = description.get(_crs_attr(key))
        expected = format_value(value)
        if actual is None:
            missing_settings.append(key)
        elif actual != expected:
            mismatched_settings.append(f"{key}: expected {expected}, got {actual}")

    missing_curves = []
    mismatched_curves = []
    for key, points in curves.items():
        actual_points = _curve_points(description, key)
        if not actual_points:
            missing_curves.append(key)
        elif list(points) != actual_points:
            mismatched_curves.append(f"{key}: expected {points}, got {actual_points}")

    required_meta = {
        "PresetType": "Normal",
        "ProcessVersion": "11.0",
        "HasSettings": "True",
    }
    missing_meta = []
    for key, expected in required_meta.items():
        actual = description.get(_crs_attr(key))
        if actual != expected:
            missing_meta.append(f"{key}: expected {expected}, got {actual}")

    if missing_settings or mismatched_settings or missing_curves or mismatched_curves or missing_meta:
        parts = []
        if missing_settings:
            parts.append("missing settings: " + ", ".join(missing_settings))
        if mismatched_settings:
            parts.append("mismatched settings: " + "; ".join(mismatched_settings))
        if missing_curves:
            parts.append("missing curves: " + ", ".join(missing_curves))
        if mismatched_curves:
            parts.append("mismatched curves: " + "; ".join(mismatched_curves))
        if missing_meta:
            parts.append("missing or invalid Lightroom preset metadata: " + "; ".join(missing_meta))
        return {
            "success": False,
            "error": "XMP validation failed: " + " | ".join(parts),
        }

    return {
        "success": True,
        "settings_count": len(settings),
        "curves_count": len(curves),
    }
