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
