# Material and formula handling

## Support matrix

| Input | Default path | Anchor | Fallback |
| --- | --- | --- | --- |
| TXT, Markdown, source, JSON/YAML, CSV/TSV | Decode and section | heading/paragraph | replacement decoding with warning |
| HTML or public web page | Safe fetch, strip markup | heading | retain raw text warning |
| PDF with text layer | pypdf text extraction | page | render selected/all pages for host vision |
| Scanned PDF | render pages | page | host vision transcription |
| PNG/JPEG/TIFF/BMP/WebP | host vision | image | unresolved image warning |
| DOCX | OOXML text parts | paragraph | optional conversion tool |
| PPTX | OOXML slide parts | slide | optional conversion tool |
| XLSX | OOXML worksheet parts | sheet | optional conversion tool |
| DOC/PPT/XLS | optional trusted converter | derived anchor | explicit unsupported issue |
| Audio/video | trusted transcript | timestamp represented as paragraph text | explicit unsupported issue |

Do not describe an optional path as installed until `scripts/check_environment.py` reports it.

## PDF and formulas

PDFs usually preserve glyphs and coordinates rather than original mathematical semantics. Treat extracted Unicode as evidence, not guaranteed LaTeX.

1. Use `--render-pdf all` for mathematics, slides, scans, multi-column layouts, or garbled extraction; otherwise use `auto`.
2. Inspect every `needs_host_vision` image. Transcribe visible text in reading order and formulas as LaTeX.
3. Keep native text and visual transcription as separate provenance. Merge only where the visual result clearly repairs ordering or symbols.
4. Preserve a formula's source ID, page/image anchor, bounding box when available, page image path, LaTeX candidate, and warnings.
5. Check balanced braces and delimiters, commands, matrix rows, subscripts/superscripts, equation numbers, nearby definitions, and source-specific index conventions. After JSON serialization and parsing, a LaTeX command must begin with one actual backslash; do not preserve a second escaping layer in the decoded value. Render LaTeX when the host has a renderer and compare it with the source crop.
6. If the transcription remains uncertain, store `status: formula_unresolved`, retain the page/image path and warning, and avoid unsupported derivation. Create one such record for each deliberately omitted ambiguous source formula; a global prose warning is not a substitute.
7. If extraction reports hidden or overlay text, record that learner-facing claims use visible page content only. Keep the hidden layer available for diagnostics but never as evidence.

MinerU may be used when already present. Never install it implicitly, require it, or call a paid/cloud OCR service without explicit user authorization.

## URL safety

Accept only public HTTP(S), reject embedded credentials and non-global resolved addresses, revalidate redirects, cap response size, apply a timeout, and record the final URL and hash. Do not circumvent authentication, authorization, robots controls, paywalls, or technical restrictions.
