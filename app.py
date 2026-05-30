import base64
import binascii
import os
from pathlib import Path
from typing import Any, List

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.datastructures import FileStorage

from image_parser import extract_from_images
from lightroom_schema import normalize_preset_payload
from xmp_builder import build_xmp
from xmp_validator import validate_xmp_content


BASE_DIR = Path(__file__).resolve().parent
MAX_FILES = int(os.environ.get("MAX_FILES", "25"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "80"))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
CORS(app)


@app.get("/")
def home():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return send_from_directory(BASE_DIR, "index.html")
    return jsonify({
        "success": True,
        "message": "Lightroom XMP Extractor API is running",
    }), 200


@app.get("/api/health")
def health():
    return jsonify({
        "success": True,
        "status": "healthy",
        "max_files": MAX_FILES,
        "max_upload_mb": MAX_UPLOAD_MB,
    }), 200


def _decode_data_url(value: str) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Empty data URL")

    if "," in value:
        value = value.split(",", 1)[1]

    try:
        return base64.b64decode(value, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image data") from exc


def _is_allowed_file(file: FileStorage) -> bool:
    suffix = Path(file.filename or "").suffix.lower()
    return suffix in ALLOWED_IMAGE_EXTENSIONS or (file.mimetype or "").startswith("image/")


def _collect_images_from_request() -> List[Any]:
    uploaded_files = [
        file for file in request.files.getlist("images")
        if file and _is_allowed_file(file)
    ]
    if uploaded_files:
        return uploaded_files[:MAX_FILES]

    payload = request.get_json(silent=True) or {}
    images = payload.get("images", [])
    if not isinstance(images, list):
        return []

    decoded_images: List[bytes] = []
    for item in images[:MAX_FILES]:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if data:
            decoded_images.append(_decode_data_url(data))

    return decoded_images


def _json_payload_without_images():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    if payload.get("images"):
        return None
    if any(key in payload for key in ("Light", "Effects", "HSL", "Curves", "settings", "canonical", "presetData")):
        return payload
    return None


@app.post("/api/process")
def process():
    try:
        direct_payload = _json_payload_without_images()

        if direct_payload is not None:
            extracted = direct_payload
            source_count = 0
        else:
            images = _collect_images_from_request()
            if not images:
                return jsonify({
                    "success": False,
                    "error": "No supported images received. Upload JPG, PNG, WEBP, TIFF, or send a JSON preset payload.",
                }), 400

            extracted = extract_from_images(images)
            source_count = len(images)

        normalized = normalize_preset_payload(extracted)
        xmp_text = build_xmp(normalized["canonical"])
        validation = validate_xmp_content(xmp_text, normalized["canonical"])

        status_code = 200 if validation["success"] else 500
        return jsonify({
            "success": validation["success"],
            "message": f"Processed {source_count} image file(s)" if source_count else "Processed JSON preset payload",
            "error": None if validation["success"] else validation["error"],
            "settings": normalized["display"],
            "canonical": normalized["canonical"],
            "detected_fields": normalized.get("detected_fields", []),
            "warnings": (extracted.get("warnings", []) if isinstance(extracted, dict) else []) + normalized.get("warnings", []),
            "sources": extracted.get("sources", []) if isinstance(extracted, dict) else [],
            "xmp": xmp_text,
            "validation": validation,
        }), status_code

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.get("/api/stats")
def stats():
    return jsonify({
        "success": True,
        "stats": {
            "max_files": MAX_FILES,
            "max_upload_mb": MAX_UPLOAD_MB,
            "supported_extensions": sorted(ALLOWED_IMAGE_EXTENSIONS),
            "supports_multipart": True,
            "supports_json_base64": True,
            "supports_direct_json_preset": True,
        },
    }), 200


@app.errorhandler(413)
def request_too_large(_):
    return jsonify({
        "success": False,
        "error": f"Upload is too large. The current limit is {MAX_UPLOAD_MB} MB.",
    }), 413


@app.errorhandler(404)
def not_found(_):
    return jsonify({
        "success": False,
        "error": "Resource not found",
    }), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({
        "success": False,
        "error": "Internal server error",
    }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
