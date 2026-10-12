"""Strict TXT decoding and codepoint locators into the unchanged attachment."""

import codecs
import hashlib
import re
from pathlib import Path
from typing import Any

from .pdf_source import ParsedSource

PARSER_VERSION = "narrative-txt-lines-v2"


def read_text_file(path: Path) -> tuple[str, str]:
    """Decode supported text encodings without replacing undecodable bytes."""
    raw = path.read_bytes()
    if not raw or raw.startswith((b"%PDF-", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8")):
        raise ValueError("The TXT attachment is empty or is not a plain text document")
    encodings: tuple[str, ...]
    if raw.startswith(codecs.BOM_UTF8):
        encodings = ("utf-8-sig",)
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8", "gb18030")
    for encoding in encodings:
        try:
            text = raw.decode(encoding, errors="strict")
        except UnicodeDecodeError:
            continue
        if not text.strip() or any(ord(char) < 32 and char not in "\r\n\t\f" for char in text):
            raise ValueError("The TXT attachment contains binary data or no readable text")
        return text, encoding
    raise ValueError("TXT encoding is not supported; use UTF-8, BOM UTF-16, or GB18030")


def parse_text(path: Path) -> ParsedSource:
    """Retain short dialogue and split long lines into bounded source segments."""
    raw, encoding = read_text_file(path)
    texts: list[str] = []
    segments: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []
    chapter = None
    chapters = []
    canonical_offset = 0
    line_start = 0
    for line_number, original_line in enumerate(raw.splitlines(keepends=True), 1):
        current_line_start = line_start
        line_start += len(original_line)
        line = original_line.strip()
        if not line:
            continue
        leading = len(original_line) - len(original_line.lstrip())
        numbered = r"第[零〇一二三四五六七八九十百千万两0-9]{1,12}[章回卷]"
        heading = re.match(rf"^({numbered}(?:\s|$)|chapter\s+\w+)", line, re.IGNORECASE)
        dash_heading = line.endswith(("——", "—")) and re.match(rf"^{numbered}", line)
        if len(line) <= 120 and (heading or dash_heading):
            chapter = line[:120]
            chapters.append(chapter)
        for part_start in range(0, len(line), 2000):
            part = line[part_start : part_start + 2000]
            text = part.strip()
            if not text:
                continue
            trim_start = len(part) - len(part.lstrip())
            source_start = current_line_start + leading + part_start + trim_start
            if texts:
                canonical_offset += 2
            segments.append(
                {
                    "ordinal": len(segments),
                    "page": None,
                    "chapter": chapter,
                    "start_offset": canonical_offset,
                    "end_offset": canonical_offset + len(text),
                    "text": text,
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            )
            locators.append(
                {
                    "page": None,
                    "page_text": text,
                    "source_start": source_start,
                    "source_end": source_start + len(text),
                    "line_number": line_number,
                }
            )
            texts.append(text)
            canonical_offset += len(text)
    if not segments:
        raise ValueError("The TXT attachment has no nonempty source segments")
    return ParsedSource(
        "\n\n".join(texts),
        segments,
        locators,
        {
            "status": "ready",
            "format": "txt",
            "encoding": encoding,
            "lines_total": len(raw.splitlines()),
            "lines_processed": len(raw.splitlines()),
            "chapter_count": len(chapters),
            "segment_count": len(segments),
            "tail_covered": True,
            "warnings": [],
            "empty_pages": [],
        },
    )
