"""Lossless line-based narrative extraction with independent PDF page locators."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParsedSource:
    text: str
    segments: list[dict[str, Any]]
    page_locators: list[dict[str, Any]]
    quality: dict[str, Any]


def sha256_file(path: Path) -> str:
    """Hash without loading the attachment into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_pdf(path: Path) -> ParsedSource:
    """Keep every nonempty extracted line, including short dialogue and margins."""
    import fitz

    texts: list[str] = []
    segments: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []
    empty_pages: list[int] = []
    image_only_pages: list[int] = []
    repeated: Counter[str] = Counter()
    offset = 0
    chapter = None
    with fitz.open(path) as document:
        total_pages = len(document)
        for number, page in enumerate(document, 1):
            raw = page.get_text("text", sort=True)
            if not raw.strip():
                empty_pages.append(number)
                if page.get_images():
                    image_only_pages.append(number)
            lines_on_page: set[str] = set()
            for match in re.finditer(r"[^\r\n]+", raw):
                line = match.group().strip()
                if not line:
                    continue
                leading = len(match.group()) - len(match.group().lstrip())
                local_start = match.start() + leading
                if re.match(r"^(第.{1,20}[章回卷]|chapter\s+\w+)", line, re.IGNORECASE):
                    chapter = line[:120]
                if texts:
                    offset += 2
                segments.append(
                    {
                        "ordinal": len(segments),
                        "page": number,
                        "chapter": chapter,
                        "start_offset": offset,
                        "end_offset": offset + len(line),
                        "text": line,
                        "text_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    }
                )
                locators.append(
                    {
                        "page": number,
                        "page_start": local_start,
                        "page_end": local_start + len(line),
                        "page_text": line,
                    }
                )
                texts.append(line)
                offset += len(line)
                lines_on_page.add(line)
            repeated.update(lines_on_page)
    needs_ocr = not segments or bool(image_only_pages)
    quality = {
        "status": "needs_ocr" if needs_ocr else "ready",
        "pages_total": total_pages,
        "pages_processed": total_pages,
        "pages_with_text": total_pages - len(empty_pages),
        "empty_pages": empty_pages,
        "image_only_pages": image_only_pages,
        "segment_count": len(segments),
        "tail_covered": bool(segments) and not image_only_pages,
        "last_text_page": segments[-1]["page"] if segments else None,
        "repeated_lines_retained": [line for line, count in repeated.most_common(32) if count > 1],
        "warnings": (["empty_pages"] if empty_pages else []) + (["needs_ocr"] if needs_ocr else []),
    }
    return ParsedSource("\n\n".join(texts), segments, locators, quality)
