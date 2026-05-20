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
