# Cambridge Semantics of Programming Languages 2025–26 — environment check

Date: 2026-08-12
Command: `.venv/bin/python skills/studykit-generator/scripts/check_environment.py`

Recorded output:

```json
{
  "jsonschema": true,
  "libreoffice_optional": false,
  "mineru_optional": false,
  "pdf_native": true,
  "pdf_visual_fallback": true,
  "pdftoppm": true,
  "pymupdf": false,
  "pypdf": true,
  "python": true,
  "pyyaml": true,
  "tesseract_optional": false
}
```

The unavailable components are optional enhancements under the StudyKit contract. The build used native prepared chunks and `pdftoppm` page rendering; no network, provider client, model endpoint, API key, or provider-backed generator was used.
