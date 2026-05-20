import os
import base64
import binascii
from typing import Any, List

from flask import Flask, jsonify, request
from flask_cors import CORS

from image_parser import extract_from_images
from lightroom_schema import normalize_preset_payload
from xmp_builder import build_xmp
from xmp_validator import validate_xmp_content

app = Flask(__name__)
CORS(app)

MAX_FILES = 25


@app.get("/")
def home():
    return jsonify({
        "success": True,
        "message": "Lightroom XMP Extractor API is running"
    }), 200


@app.get("/api/health")
def health():
    return jsonify({
        "success": True,
        "status": "healthy"
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


def _collect_images() -> List[Any]:
    """
    Supports:
    1) multipart/form-data with files under key: images
    2) application/json with images=[{name,data}, ...]
    """
    uploaded_files = request.files.getlist("images")
    if uploaded_files:
        return uploaded_files[:MAX_FILES]

    payload = request.get_json(silent=True) or {}
    images = payload.get("images", [])

    if not isinstance(images, list) or not images:
        return []

    decoded_images: List[bytes] = []
    for item in images[:MAX_FILES]:
        if not isinstance(item, dict):
            continue

        data = item.get("data")
        if not data:
            continue

        decoded_images.append(_decode_data_url(data))

    return decoded_images


@app.post("/api/process")
def process():
    try:
        images = _collect_images()

        if not images:
            return jsonify({
                "success": False,
                "error": "No images received"
            }), 400

        extracted = extract_from_images(images)
        normalized = normalize_preset_payload(extracted)

        xmp_text = build_xmp(normalized["canonical"])
        validation = validate_xmp_content(xmp_text, normalized["canonical"])

        if not validation["success"]:
            return jsonify({
                "success": False,
                "error": validation["error"],
                "settings": normalized["display"],
                "canonical": normalized["canonical"],
                "sources": extracted.get("sources", [])
            }), 500

        return jsonify({
            "success": True,
            "message": f"Processed {len(images)} file(s)",
            "settings": normalized["display"],
            "canonical": normalized["canonical"],
            "sources": extracted.get("sources", []),
            "xmp": xmp_text,
            "validation": validation
        }), 200

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


@app.get("/api/stats")
def stats():
    return jsonify({
        "success": True,
        "stats": {
            "max_files": MAX_FILES,
            "supports_multipart": True,
            "supports_json_base64": True
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
