# Lightroom XMP Extractor

Flask app that converts Lightroom Mobile setting screenshots into an Adobe Camera Raw / Lightroom compatible `.xmp` preset.

## Data flow

1. Browser uploads screenshots as `multipart/form-data` under the key `images`.
2. `app.py` sends the images to `image_parser.extract_from_images`.
3. `image_parser.py` uses OCR for visible slider values and computer-vision helpers for HSL color tabs and point-curve screenshots.
4. `lightroom_schema.py` normalizes display values into real Adobe `crs:*` keys.
5. `xmp_builder.py` serializes the canonical payload as RDF/XMP using Lightroom preset metadata and curve sequences.
6. `xmp_validator.py` parses the generated XML and verifies that every canonical setting and curve exists in the final XMP.

## Deployment notes

Python dependencies are in `requirements.txt`.

`pytesseract` also needs the system Tesseract binary. On Render-style deployments, keep `Aptfile` in the repo:

```txt
tesseract-ocr
tesseract-ocr-eng
```

Use the real `Procfile` filename, not `Procfile.txt`:

```txt
web: gunicorn app:app
```

## Known limitation

Lightroom Mobile parametric curve screenshots show a rendered curve but hide the numeric parametric slider values. The app does not invent those hidden values. Point-curve screenshots can be estimated from visible control points; exact parametric values need screenshots or OCR text that exposes the numeric sliders.
