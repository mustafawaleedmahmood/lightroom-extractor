"""
xmp_validator.py
================
Validates a generated XMP string against the canonical preset payload.

FIX: ToneCurveName2012 is computed at build time (based on actual curve
     data), so the validator now derives the expected value from curves
     instead of blindly reading it from canonical["settings"] (which
     defaults to "Linear" regardless of curve content).
"""

from xml.etree import ElementTree as ET

from lightroom_schema import CRS_NS, DEFAULT_CURVES, RDF_NS
from xmp_builder import format_setting


def _crs_attr(name):
    return f"{{{CRS_NS}}}{name}"


def _find_description(root):
    return root.find(f".//{{{RDF_NS}}}Description")


def _curve_points(description, curve_name):
    curve = description.find(f"{{{CRS_NS}}}{curve_name}")
    if curve is None:
        return []
    return [(li.text or "").strip() for li in curve.findall(f".//{{{RDF_NS}}}li")]


def _is_linear(points):
    return list(points or []) == ["0, 0", "255, 255"]


def _expected_curve_name(curves):
    """Derive the ToneCurveName2012 that build_xmp would write."""
    for pts in curves.values():
        if not _is_linear(pts):
            return "Custom"
    return "Linear"


def _values_equivalent(a, b):
    """
    Numeric-aware equality: "0" == "0.00" == "0.0", "-5" == "-5.0", etc.
    Falls back to exact string match.
    """
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        return False


def validate_xmp_content(xmp_text: str, canonical: dict) -> dict:
    """
    Parse xmp_text and verify it contains all settings and curves from canonical.

    Returns {"success": True, ...} or {"success": False, "error": "..."}.
    """
    if not isinstance(xmp_text, str) or not xmp_text.strip():
        return {"success": False, "error": "Generated XMP is empty"}

    try:
        root = ET.fromstring(xmp_text.encode("utf-8"))
    except ET.ParseError as exc:
        return {"success": False, "error": f"Generated XMP is not valid XML: {exc}"}

    description = _find_description(root)
    if description is None:
        return {"success": False, "error": "Generated XMP does not contain rdf:Description"}

    settings = canonical.get("settings", {})
    curves   = {**DEFAULT_CURVES, **canonical.get("curves", {})}

    # ------------------------------------------------------------------
    # Build the authoritative expected values the same way build_xmp does
    # ------------------------------------------------------------------
    expected_curve_name = _expected_curve_name(curves)

    missing_settings    = []
    mismatched_settings = []

    for key, value in settings.items():
        # ToneCurveName2012 must be computed from curves, NOT from canonical["settings"]
        if key == "ToneCurveName2012":
            expected = expected_curve_name
        else:
            expected = format_setting(key, value)

        actual = description.get(_crs_attr(key))
        if actual is None:
            missing_settings.append(key)
        elif not _values_equivalent(actual, expected):
            mismatched_settings.append(
                f"{key}: expected {expected!r}, got {actual!r}"
            )

    missing_curves    = []
    mismatched_curves = []

    for key, points in curves.items():
        actual_points = _curve_points(description, key)
        if not actual_points:
            missing_curves.append(key)
        elif list(points) != actual_points:
            mismatched_curves.append(
                f"{key}: expected {points}, got {actual_points}"
            )

    # Core Lightroom preset metadata
    required_meta = {
        "PresetType":   "Normal",
        "ProcessVersion": "11.0",
        "HasSettings":  "True",
    }
    meta_errors = []
    for key, expected in required_meta.items():
        actual = description.get(_crs_attr(key))
        if actual != expected:
            meta_errors.append(f"{key}: expected {expected!r}, got {actual!r}")

    problems = []
    if missing_settings:
        problems.append("missing settings: " + ", ".join(missing_settings))
    if mismatched_settings:
        problems.append("mismatched settings: " + "; ".join(mismatched_settings))
    if missing_curves:
        problems.append("missing curves: " + ", ".join(missing_curves))
    if mismatched_curves:
        problems.append("mismatched curves: " + "; ".join(mismatched_curves))
    if meta_errors:
        problems.append("preset metadata errors: " + "; ".join(meta_errors))

    if problems:
        return {"success": False, "error": "XMP validation failed: " + " | ".join(problems)}

    return {
        "success":       True,
        "settings_count": len(settings),
        "curves_count":   len(curves),
    }
