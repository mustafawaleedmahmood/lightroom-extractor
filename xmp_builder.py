from xml.dom import minidom
from xml.etree import ElementTree as ET

from lightroom_schema import (
    CRS_NS,
    DEFAULT_CURVES,
    DEFAULT_META,
    DEFAULT_SETTINGS,
    RDF_NS,
    X_NS,
    normalize_preset_payload,
)


ET.register_namespace("x", X_NS)
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("crs", CRS_NS)

XML_NS = "http://www.w3.org/XML/1998/namespace"


META_ATTRIBUTE_ORDER = [
    "PresetType",
    "Cluster",
    "UUID",
    "SupportsAmount",
    "SupportsColor",
    "SupportsMonochrome",
    "SupportsHighDynamicRange",
    "SupportsNormalDynamicRange",
    "SupportsSceneReferred",
    "SupportsOutputReferred",
    "CameraModelRestriction",
    "Copyright",
    "ContactInfo",
    "Version",
    "ProcessVersion",
]


SETTING_ATTRIBUTE_ORDER = list(DEFAULT_SETTINGS.keys())


def _crs_attr(name):
    return f"{{{CRS_NS}}}{name}"


def _rdf_attr(name):
    return f"{{{RDF_NS}}}{name}"


def _crs_tag(name):
    return f"{{{CRS_NS}}}{name}"


def _rdf_tag(name):
    return f"{{{RDF_NS}}}{name}"


def _xml_attr(name):
    return f"{{{XML_NS}}}{name}"


def format_value(value):
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _is_linear_curve(points):
    return list(points or []) == ["0, 0", "255, 255"]


def _append_localized_alt(parent, tag_name, text=""):
    container = ET.SubElement(parent, _crs_tag(tag_name))
    alt = ET.SubElement(container, _rdf_tag("Alt"))
    li = ET.SubElement(alt, _rdf_tag("li"), {_xml_attr("lang"): "x-default"})
    li.text = text or ""
    return container


def _append_curve(description, curve_name, points):
    curve = ET.SubElement(description, _crs_tag(curve_name))
    seq = ET.SubElement(curve, _rdf_tag("Seq"))
    for point in points:
        li = ET.SubElement(seq, _rdf_tag("li"))
        li.text = str(point)


def _prettify(root):
    raw = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    lines = [
        line for line in pretty.decode("utf-8").splitlines()
        if line.strip()
    ]
    return "\n".join(lines) + "\n"


def build_xmp(preset):
    """
    Build a Lightroom-compatible XMP preset from the canonical payload:
    {
        "meta": {...},
        "settings": {"Exposure2012": 0.8, ...},
        "curves": {"ToneCurvePV2012": ["0, 0", "255, 255"], ...}
    }
    Display-shaped payloads are accepted and normalized before serialization.
    """
    normalized = normalize_preset_payload(preset).get("canonical", {})

    meta = {**DEFAULT_META, **normalized.get("meta", {})}
    settings = {**DEFAULT_SETTINGS, **normalized.get("settings", {})}
    curves = {**DEFAULT_CURVES, **normalized.get("curves", {})}

    any_custom_curve = any(
        not _is_linear_curve(points)
        for points in curves.values()
    )
    settings["ToneCurveName2012"] = "Custom" if any_custom_curve else "Linear"

    xmpmeta = ET.Element(
        f"{{{X_NS}}}xmpmeta",
        {f"{{{X_NS}}}xmptk": "Adobe XMP Core"},
    )
    rdf = ET.SubElement(xmpmeta, _rdf_tag("RDF"))
    description = ET.SubElement(rdf, _rdf_tag("Description"), {_rdf_attr("about"): ""})

    for key in META_ATTRIBUTE_ORDER:
        if key in meta and meta[key] not in (None, ""):
            description.set(_crs_attr(key), format_value(meta[key]))

    for key in SETTING_ATTRIBUTE_ORDER:
        if key in settings and settings[key] not in (None, ""):
            description.set(_crs_attr(key), format_value(settings[key]))

    description.set(_crs_attr("HasSettings"), "True")

    _append_localized_alt(description, "Name", meta.get("Name", "Extracted Lightroom Preset"))
    _append_localized_alt(description, "ShortName", meta.get("ShortName", ""))
    _append_localized_alt(description, "SortName", meta.get("SortName", ""))
    _append_localized_alt(description, "Group", meta.get("Group", "User Presets"))
    _append_localized_alt(description, "Description", meta.get("Description", ""))

    for curve_name in DEFAULT_CURVES.keys():
        points = curves.get(curve_name) or DEFAULT_CURVES[curve_name]
        _append_curve(description, curve_name, points)

    ET.SubElement(description, _crs_tag("Look"), {_crs_attr("Name"): ""})

    return _prettify(xmpmeta)
