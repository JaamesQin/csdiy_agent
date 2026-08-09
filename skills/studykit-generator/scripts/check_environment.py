#!/usr/bin/env python3
"""Report optional capabilities without installing anything."""

from __future__ import annotations

import importlib.util
import json
import shutil


def main() -> None:
    capabilities = {
        "python": True,
        "pypdf": importlib.util.find_spec("pypdf") is not None,
        "jsonschema": importlib.util.find_spec("jsonschema") is not None,
        "pyyaml": importlib.util.find_spec("yaml") is not None,
        "pymupdf": importlib.util.find_spec("pymupdf") is not None,
        "mineru_optional": importlib.util.find_spec("mineru") is not None,
        "pdftoppm": shutil.which("pdftoppm") is not None,
        "tesseract_optional": shutil.which("tesseract") is not None,
        "libreoffice_optional": shutil.which("soffice") is not None,
    }
    capabilities["pdf_native"] = capabilities["pypdf"]
    capabilities["pdf_visual_fallback"] = capabilities["pdftoppm"] or capabilities["pymupdf"]
    print(json.dumps(capabilities, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
