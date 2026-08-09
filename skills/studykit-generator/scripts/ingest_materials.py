#!/usr/bin/env python3
"""Inventory and extract course materials without calling a model or API."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import mimetypes
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET
import zipfile


PARSER_VERSION = "studykit-ingest-v0.1.0"
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".tex", ".bib", ".csv", ".tsv",
    ".json", ".jsonl", ".yaml", ".yml", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".java", ".c", ".cc", ".cpp", ".h", ".hpp", ".go", ".rs",
    ".sh", ".sql", ".r", ".m", ".scala", ".kt", ".ipynb",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
MATH_HINT = re.compile(
    r"(?:[=+−×÷∑∏∫√∂∇≠≤≥∞α-ωΑ-Ω]"
    r"|\\(?:frac|sum|int|sqrt|begin|alpha|beta|gamma|theta|lambda)\b)"
)


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "br", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return _normalize_text(html.unescape("".join(self.parts)))


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _normalize_text(value: str) -> str:
    value = re.sub(r"[\ud800-\udfff]", "\ufffd", value)
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in value.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:40] or "source"


def _source_id(path: Path, digest: str) -> str:
    return f"{_slug(path.stem)}-{digest[:10]}"


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public http/https URLs are accepted")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are rejected")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f"hostname resolution failed: {exc}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global:
            raise ValueError(f"URL resolves to a non-public address: {ip}")


def _download(url: str, destination: Path, max_bytes: int, timeout: float) -> Path:
    _validate_public_url(url)
    request = Request(url, headers={"User-Agent": "studykit-generator/0.1"})
    with build_opener(_SafeRedirect()).open(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError(f"remote file exceeds {max_bytes} bytes")
        suffix = Path(urlparse(response.geturl()).path).suffix.lower()
        if not suffix:
            suffix = mimetypes.guess_extension(response.headers.get_content_type()) or ".bin"
        target = destination / f"url-{hashlib.sha256(url.encode()).hexdigest()[:12]}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with target.open("wb") as stream:
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > max_bytes:
                    raise ValueError(f"remote file exceeds {max_bytes} bytes")
                stream.write(block)
    return target


def _chunk(source_id: str, anchor_type: str, anchor_value: int | str, content: str,
           *, material_set_id: str, scope: str, owner_id: str | None,
           course_id: str | None, course_version: str | None, unit_id: str,
           heading: str | None = None, warnings: Iterable[str] = ()) -> dict[str, Any]:
    anchor_slug = _slug(str(anchor_value))[:24]
    return {
        "chunk_id": f"{source_id}-{anchor_type}-{anchor_slug}",
        "material_set_id": material_set_id,
        "scope": scope,
        "owner_id": owner_id,
        "course_id": course_id,
        "course_version": course_version,
        "unit_id": unit_id,
        "source_id": source_id,
        "anchor": {"type": anchor_type, "value": anchor_value},
        "heading": heading,
        "content": content,
        "content_type": "mixed" if MATH_HINT.search(content) else "text",
        "parser_version": PARSER_VERSION,
        "parse_warnings": list(warnings),
    }


def _decode(path: Path) -> tuple[str, list[str]]:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            text = data.decode(encoding)
            return _normalize_text(text), ([] if encoding == "utf-8" else [f"decoded_as:{encoding}"])
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), ["decode_replacement_characters"]


def _parse_text(path: Path, source_id: str, context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    text, warnings = _decode(path)
    if path.suffix.lower() in {".html", ".htm"}:
        parser = _HTMLText()
        parser.feed(text)
        text = parser.text()
    chunks: list[dict[str, Any]] = []
    sections = re.split(r"(?m)(?=^#{1,6}\s+|^\S.{0,100}\n[=-]{3,}\s*$)", text)
    for index, section in enumerate(filter(str.strip, sections), start=1):
        first = section.strip().splitlines()[0][:160]
        chunks.append(_chunk(source_id, "heading", first or f"section-{index}", section, heading=first, warnings=warnings, **context))
    if not chunks:
        chunks.append(_chunk(source_id, "paragraph", 1, text, warnings=[*warnings, "empty_or_unstructured_text"], **context))
    return chunks, [], warnings


def _xml_text(data: bytes) -> str:
    root = ET.fromstring(data)
    values = [node.text for node in root.iter() if node.text and node.tag.rsplit("}", 1)[-1] in {"t", "instrText"}]
    return _normalize_text(" ".join(values))


def _parse_ooxml(path: Path, source_id: str, context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    suffix = path.suffix.lower()
    patterns = {
        ".docx": ("word/", "paragraph"),
        ".pptx": ("ppt/slides/slide", "slide"),
        ".xlsx": ("xl/worksheets/sheet", "sheet"),
    }
    prefix, anchor_type = patterns[suffix]
    chunks: list[dict[str, Any]] = []
    warnings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(name for name in archive.namelist() if name.startswith(prefix) and name.endswith(".xml"))
        if suffix == ".docx":
            names = [name for name in names if name == "word/document.xml"]
        elif suffix == ".xlsx" and "xl/sharedStrings.xml" in archive.namelist():
            names.insert(0, "xl/sharedStrings.xml")
        for index, name in enumerate(names, start=1):
            try:
                content = _xml_text(archive.read(name))
            except ET.ParseError:
                warnings.append(f"invalid_xml_part:{name}")
                continue
            if content:
                chunks.append(_chunk(source_id, anchor_type, index, content, heading=Path(name).stem, **context))
    if not chunks:
        warnings.append("no_extractable_ooxml_text")
    return chunks, [], warnings


def _render_pdf_page(path: Path, page: int, destination: Path) -> str | None:
    executable = shutil.which("pdftoppm")
    if not executable:
        return None
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / f"page-{page:04d}"
    result = subprocess.run(
        [executable, "-f", str(page), "-singlefile", "-r", "200", "-png", str(path), str(prefix)],
        capture_output=True, text=True, check=False,
    )
    output = prefix.with_suffix(".png")
    return str(output) if result.returncode == 0 and output.is_file() else None


def _parse_pdf(path: Path, source_id: str, context: dict[str, Any], render_mode: str, render_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF extraction") from exc
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("encrypted PDF is unsupported")
    chunks: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    warnings: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = _normalize_text(page.extract_text() or "")
        page_warnings: list[str] = []
        low_text = len(text) < 40
        math_hint = bool(MATH_HINT.search(text))
        if low_text:
            page_warnings.append("low_extracted_text")
        should_render = render_mode == "all" or (render_mode == "auto" and (low_text or math_hint))
        image_path = _render_pdf_page(path, page_number, render_root / source_id) if should_render else None
        if should_render and image_path is None:
            page_warnings.append("pdf_renderer_unavailable")
        chunks.append(_chunk(source_id, "page", page_number, text, heading=(text.splitlines()[0][:160] if text else None), warnings=page_warnings, **context))
        if low_text or math_hint:
            formulas.append({
                "source_id": source_id,
                "page": page_number,
                "page_image": image_path,
                "native_text": text,
                "reason": "low_text" if low_text else "math_symbols_detected",
                "action": "use_host_vision_to_transcribe_math_as_latex",
                "status": "needs_host_vision" if image_path else "native_text_only",
            })
    return chunks, formulas, warnings


def _parse_image(path: Path, source_id: str, context: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    candidate = {
        "source_id": source_id,
        "page": 1,
        "page_image": str(path.resolve()),
        "native_text": "",
        "reason": "image_input",
        "action": "use_host_vision_to_transcribe_text_and_math_with_regions",
        "status": "needs_host_vision",
    }
    chunk = _chunk(source_id, "image", 1, "", warnings=["host_vision_required"], **context)
    return [chunk], [candidate], ["host_vision_required"]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material", type=Path, action="append", default=[])
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--material-set-id", default="material-set-candidate")
    parser.add_argument("--course-id")
    parser.add_argument("--course-version")
    parser.add_argument("--unit-id", default="unassigned")
    parser.add_argument("--scope", choices=("public", "private"), default="private")
    parser.add_argument("--owner-id", default="local-user")
    parser.add_argument("--render-pdf", choices=("auto", "all", "none"), default="auto")
    parser.add_argument("--max-url-bytes", type=int, default=50 * 1024 * 1024)
    parser.add_argument("--url-timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.material and not args.url:
        print("at least one --material or --url is required", file=sys.stderr)
        return 2
    if args.scope == "public":
        args.owner_id = None
    elif not args.owner_id:
        print("private scope requires --owner-id", file=sys.stderr)
        return 2
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    downloads = output / "_downloads"
    inputs: list[tuple[Path, str | None]] = []
    issues: list[dict[str, Any]] = []
    failed_url_records: list[dict[str, Any]] = []
    for path in args.material:
        inputs.append((path.resolve(), None))
    for url in args.url:
        try:
            inputs.append((_download(url, downloads, args.max_url_bytes, args.url_timeout), url))
        except Exception as exc:
            issues.append({"source": url, "code": "url_fetch_failed", "message": str(exc)})
            failed_url_records.append({"input": url, "local_path": None, "status": "failed", "error": str(exc)})

    all_chunks: list[dict[str, Any]] = []
    formula_candidates: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = list(failed_url_records)
    context = {
        "material_set_id": args.material_set_id, "scope": args.scope,
        "owner_id": args.owner_id, "course_id": args.course_id,
        "course_version": args.course_version, "unit_id": args.unit_id,
    }
    for path, original_url in inputs:
        record: dict[str, Any] = {"input": original_url or str(path), "local_path": str(path), "status": "failed"}
        try:
            if not path.is_file():
                raise ValueError("input is not a readable file")
            digest = _sha256(path)
            source_id = _source_id(path, digest)
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                chunks, formulas, warnings = _parse_pdf(path, source_id, context, args.render_pdf, output / "page-images")
            elif suffix in {".docx", ".pptx", ".xlsx"}:
                chunks, formulas, warnings = _parse_ooxml(path, source_id, context)
            elif suffix in IMAGE_EXTENSIONS:
                chunks, formulas, warnings = _parse_image(path, source_id, context)
            elif suffix in TEXT_EXTENSIONS or suffix in {".html", ".htm"}:
                chunks, formulas, warnings = _parse_text(path, source_id, context)
            else:
                raise ValueError(f"unsupported file type: {suffix or 'no extension'}")
            all_chunks.extend(chunks)
            formula_candidates.extend(formulas)
            record.update({
                "source_id": source_id, "sha256": digest, "media_type": mimetypes.guess_type(path.name)[0],
                "size_bytes": path.stat().st_size, "status": "parsed" if chunks else "partial",
                "chunk_count": len(chunks), "warnings": warnings,
            })
        except Exception as exc:
            issues.append({"source": original_url or str(path), "code": "ingestion_failed", "message": str(exc)})
            record["error"] = str(exc)
        sources.append(record)

    status = "succeeded" if all_chunks and not issues else ("partial" if all_chunks else "ingestion_failed")
    report = {
        "version": "0.1.0", "parser_version": PARSER_VERSION, "status": status,
        "source_count": len(sources), "parsed_source_count": sum(s.get("status") != "failed" for s in sources),
        "chunk_count": len(all_chunks), "formula_candidate_count": len(formula_candidates),
        "sources": sources, "issues": issues,
        "next_action": "complete_host_vision_then_group_courses_and_units" if formula_candidates else "group_courses_and_units",
    }
    _write_jsonl(output / "chunks.jsonl", all_chunks)
    _write_json(output / "formula-candidates.json", formula_candidates)
    _write_json(output / "ingestion-report.json", report)
    print(json.dumps({"status": status, "output_dir": str(output), "chunks": len(all_chunks), "issues": len(issues)}))
    return 0 if status in {"succeeded", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
