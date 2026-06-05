"""
app.py
======
Flask backend for the Lightroom XMP Extractor.

Data flow:
  POST /api/process
    → extract_from_images  (OCR + CV)  [or accept direct JSON preset]
    → normalize_preset_payload         (display → canonical)
    → build_xmp                        (canonical → XMP string)
    → validate_xmp_content             (verify every setting made it in)
    → JSON response  {success, settings, xmp, ...}
"""

import base64
import binascii
import logging
import os
from pathlib import Path
from typing import Any, List

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.datastructures import FileStorage

from image_parser import extract_from_images
from lightroom_schema import DEFAULT_CURVES, normalize_preset_payload
from xmp_builder import build_xmp
from xmp_validator import validate_xmp_content

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------
BASE_DIR       = Path(__file__).resolve().parent
MAX_FILES      = int(os.environ.get("MAX_FILES",     "25"))
MAX_UPLOAD_MB  = int(os.environ.get("MAX_UPLOAD_MB", "80"))
ALLOWED_EXTS   = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
CORS(app)


# ---------------------------------------------------------------------------
# Static routes
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return send_from_directory(BASE_DIR, "index.html")
    return jsonify({"success": True, "message": "Lightroom XMP Extractor API is running"}), 200


@app.get("/api/health")
def health():
    return jsonify({
        "success":       True,
        "status":        "healthy",
        "max_files":     MAX_FILES,
        "max_upload_mb": MAX_UPLOAD_MB,
    }), 200


@app.get("/api/stats")
def stats():
    return jsonify({
        "success": True,
        "stats": {
            "max_files":              MAX_FILES,
            "max_upload_mb":          MAX_UPLOAD_MB,
            "supported_extensions":   sorted(ALLOWED_EXTS),
            "supports_multipart":     True,
            "supports_json_base64":   True,
            "supports_direct_json":   True,
        },
    }), 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_data_url(value: str) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Empty data URL")
    if "," in value:
        value = value.split(",", 1)[1]
    try:
        return base64.b64decode(value, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image data") from exc


def _is_allowed(file: FileStorage) -> bool:
    ext  = Path(file.filename or "").suffix.lower()
    mime = (file.mimetype or "")
    return ext in ALLOWED_EXTS or mime.startswith("image/")


def _collect_images() -> List[Any]:
    files = [f for f in request.files.getlist("images") if f and _is_allowed(f)]
    if files:
        return files[:MAX_FILES]

    payload = request.get_json(silent=True) or {}
    items   = payload.get("images", [])
    if not isinstance(items, list):
        return []

    decoded: List[bytes] = []
    for item in items[:MAX_FILES]:
        if isinstance(item, dict) and item.get("data"):
            try:
                decoded.append(_decode_data_url(item["data"]))
            except ValueError as exc:
                log.warning("Skipping malformed base64 image: %s", exc)
    return decoded


def _direct_json_preset():
    """Return the JSON body if it is a preset payload (not an image upload)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("images"):
        return None
    preset_keys = ("Light", "Effects", "HSL", "Curves",
                   "settings", "canonical", "presetData")
    if any(k in payload for k in preset_keys):
        return payload
    return None


# ---------------------------------------------------------------------------
# Main processing endpoint
# ---------------------------------------------------------------------------

@app.post("/api/process")
def process():
    try:
        direct = _direct_json_preset()

        if direct is not None:
            log.info("Processing direct JSON preset payload.")
            extracted    = direct
            source_count = 0
        else:
            images = _collect_images()
            if not images:
                return jsonify({
                    "success": False,
                    "error":   "No supported images received. "
                               "Upload JPG/PNG/WEBP/TIFF or send a JSON preset payload.",
                }), 400
            log.info("Processing %d image file(s).", len(images))
            extracted    = extract_from_images(images)
            source_count = len(images)

        # 1. Normalize display/raw data → canonical
        normalized = normalize_preset_payload(extracted)
        canonical  = normalized["canonical"]

        log.info(
            "Detected %d fields. Warnings: %s",
            len(normalized.get("detected_fields", [])),
            normalized.get("warnings") or "none",
        )

        # 2. Build XMP  (build_xmp sets ToneCurveName2012 from actual curves)
        xmp_text = build_xmp(canonical)

        # 3. Validate
        validation = validate_xmp_content(xmp_text, canonical)
        if not validation["success"]:
            log.error("XMP validation failed: %s", validation.get("error"))
        else:
            log.info(
                "XMP validated OK — %d settings, %d curves.",
                validation.get("settings_count", 0),
                validation.get("curves_count", 0),
            )

        status = 200 if validation["success"] else 500
        return jsonify({
            "success":         validation["success"],
            "message":         (
                f"Processed {source_count} image file(s)"
                if source_count else "Processed JSON preset payload"
            ),
            "error":           None if validation["success"] else validation.get("error"),
            "settings":        normalized["display"],
            "canonical":       canonical,
            "detected_fields": normalized.get("detected_fields", []),
            "warnings":        (
                (extracted.get("warnings", []) if isinstance(extracted, dict) else [])
                + normalized.get("warnings", [])
            ),
            "sources":         extracted.get("sources", []) if isinstance(extracted, dict) else [],
            "xmp":             xmp_text,
            "validation":      validation,
        }), status

    except Exception as exc:
        log.exception("Unhandled error in /api/process: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(413)
def request_too_large(_):
    return jsonify({
        "success": False,
        "error":   f"Upload too large — limit is {MAX_UPLOAD_MB} MB.",
    }), 413


@app.errorhandler(404)
def not_found(_):
    return jsonify({"success": False, "error": "Resource not found."}), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({"success": False, "error": "Internal server error."}), 500


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,
            debug=os.environ.get("FLASK_DEBUG") == "1")
