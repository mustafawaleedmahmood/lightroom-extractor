"""
xmp_builder.py
==============
Builds a Lightroom-compatible XMP preset from a **canonical** payload:

    {
        "meta":     { "Name": "...", "UUID": "...", ... },
        "settings": { "Exposure2012": 0.8, "GrainAmount": 30, ... },
        "curves":   { "ToneCurvePV2012": ["0, 0", "255, 255"], ... }
    }

Call build_xmp(canonical) directly — no secondary normalization is performed.
"""

from xml.dom import minidom
from xml.etree import ElementTree as ET

from lightroom_schema import (
    CRS_NS,
    DEFAULT_CURVES,
    DEFAULT_META,
    DEFAULT_SETTINGS,
    RDF_NS,
    STRING_FORMAT_KEYS,
    X_NS,
)

ET.register_namespace("x",   X_NS)
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("crs", CRS_NS)

XML_NS = "http://www.w3.org/XML/1998/namespace"

META_ATTRIBUTE_ORDER = [
    "PresetType", "Cluster", "UUID",
    "SupportsAmount", "SupportsColor", "SupportsMonochrome",
    "SupportsHighDynamicRange", "SupportsNormalDynamicRange",
    "SupportsSceneReferred", "SupportsOutputReferred",
    "CameraModelRestriction", "Copyright", "ContactInfo",
    "Version", "ProcessVersion",
]

SETTING_ATTRIBUTE_ORDER = list(DEFAULT_SETTINGS.keys())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crs_attr(name):   return f"{{{CRS_NS}}}{name}"
def _rdf_attr(name):   return f"{{{RDF_NS}}}{name}"
def _crs_tag(name):    return f"{{{CRS_NS}}}{name}"
def _rdf_tag(name):    return f"{{{RDF_NS}}}{name}"
def _xml_attr(name):   return f"{{{XML_NS}}}{name}"


def format_setting(key, value):
    """
    Convert a (key, value) pair to the exact string Lightroom expects in XMP.

    Rules:
    • bool  → "True" / "False"
    • STRING_FORMAT_KEYS → preserve / re-derive the specific string format
      - SharpenRadius  : "+N.N" (always with leading '+')
      - PerspectiveRotate : "N.N"  (one decimal)
      - PerspectiveX / PerspectiveY : "N.NN" (two decimals)
    • float → strip unnecessary trailing zeros
    • int / str → str()
    """
    if isinstance(value, bool):
        return "True" if value else "False"

    if key in STRING_FORMAT_KEYS:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return str(value)
        if key == "SharpenRadius":
            return f"+{f:.1f}"          # always "+1.0" style
        if key == "PerspectiveRotate":
            return f"{f:.1f}"           # "0.0"
        if key in ("PerspectiveX", "PerspectiveY"):
            return f"{f:.2f}"           # "0.00"

    if isinstance(value, float):
        # Compact decimal: 0.8 not 0.80; -5.0 → -5; 0.25 → 0.25
        s = f"{value:.6f}".rstrip("0").rstrip(".")
        return s

    return str(value)


def _is_linear_curve(points):
    return list(points or []) == ["0, 0", "255, 255"]


def _append_localized_alt(parent, tag_name, text=""):
    container = ET.SubElement(parent, _crs_tag(tag_name))
    alt = ET.SubElement(container, _rdf_tag("Alt"))
    li  = ET.SubElement(alt, _rdf_tag("li"), {_xml_attr("lang"): "x-default"})
    li.text = text or ""
    return container


def _append_curve(description, curve_name, points):
    curve = ET.SubElement(description, _crs_tag(curve_name))
    seq   = ET.SubElement(curve,       _rdf_tag("Seq"))
    for point in points:
        li      = ET.SubElement(seq, _rdf_tag("li"))
        li.text = str(point)


def _prettify(root):
    raw   = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    lines  = [ln for ln in pretty.decode("utf-8").splitlines() if ln.strip()]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_xmp(canonical: dict) -> str:
    """
    Build a Lightroom-compatible XMP string from a canonical payload.

    Parameters
    ----------
    canonical : dict
        Output of normalize_preset_payload(...)["canonical"].
        Keys: "meta", "settings", "curves".

    Returns
    -------
    str  – UTF-8 XML ready to write to a .xmp file.
    """
    meta     = {**DEFAULT_META,   **canonical.get("meta",     {})}
    settings = {**DEFAULT_SETTINGS, **canonical.get("settings", {})}
    curves   = {**DEFAULT_CURVES,   **canonical.get("curves",   {})}

    # Determine curve name from actual curve data (not from canonical["settings"])
    any_custom = any(not _is_linear_curve(pts) for pts in curves.values())
    settings["ToneCurveName2012"] = "Custom" if any_custom else "Linear"

    # -----------------------------------------------------------------------
    # Build XML tree
    # -----------------------------------------------------------------------
    xmpmeta = ET.Element(
        f"{{{X_NS}}}xmpmeta",
        {f"{{{X_NS}}}xmptk": "Adobe XMP Core 5.6-c140 79.160924, 2017/11/10-18:12:15"},
    )
    rdf         = ET.SubElement(xmpmeta,  _rdf_tag("RDF"))
    description = ET.SubElement(rdf,      _rdf_tag("Description"), {_rdf_attr("about"): ""})

    # -- Preset metadata attributes --
    for key in META_ATTRIBUTE_ORDER:
        val = meta.get(key)
        if val is None or val == "":
            continue
        description.set(_crs_attr(key), format_setting(key, val))

    # -- All slider / adjustment settings --
    for key in SETTING_ATTRIBUTE_ORDER:
        val = settings.get(key)
        if val is None or val == "":
            continue
        description.set(_crs_attr(key), format_setting(key, val))

    # HasSettings must always be True for a valid Lightroom preset
    description.set(_crs_attr("HasSettings"), "True")

    # -- Localized text child elements --
    _append_localized_alt(description, "Name",        meta.get("Name",        "Extracted Lightroom Preset"))
    _append_localized_alt(description, "ShortName",   meta.get("ShortName",   ""))
    _append_localized_alt(description, "SortName",    meta.get("SortName",    ""))
    _append_localized_alt(description, "Group",       meta.get("Group",       "User Presets"))
    _append_localized_alt(description, "Description", meta.get("Description", ""))

    # -- Tone curve sequences --
    for curve_name in DEFAULT_CURVES:
        pts = curves.get(curve_name) or DEFAULT_CURVES[curve_name]
        _append_curve(description, curve_name, pts)

    # Look element (required by Lightroom schema)
    ET.SubElement(description, _crs_tag("Look"), {_crs_attr("Name"): ""})

    return _prettify(xmpmeta)
