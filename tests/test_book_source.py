"""BookSourceService behavior in disposable workspaces and real PDF files."""

from pathlib import Path

import fitz
import pytest

from backend.services.book_world import BookSourceService, BookWorldError
from backend.services.knowledge_migrations import run_knowledge_index_migrations
from backend.services.library_engine import LibraryEngine


@pytest.fixture
def library(tmp_path: Path):
    run_knowledge_index_migrations(tmp_path / "knowledge" / ".knowledge_index.db")
    engine = LibraryEngine(str(tmp_path))
    yield engine
    engine.db.close()
    LibraryEngine._instances.pop(str(tmp_path.resolve()), None)


def add_pdf(library: LibraryEngine, pages: list[list[str]]) -> dict:
    item = library.create_item(metadata={"title": "Original test novel", "item_type": "book"})
    path = library.workspace_root / item["library_path"] / "main.pdf"
    with fitz.open() as document:
        for lines in pages:
            page = document.new_page()
            for index, line in enumerate(lines):
                page.insert_text((40, 45 + index * 18), line, fontname="china-s", fontsize=11)
        document.save(path)
    library.db.execute(
        "UPDATE library_items SET pdf_sha256=?,chunk_status='completed' WHERE id=?",
        (library._compute_sha256(path), item["id"]),
    )
    library.db.commit()
    return library.get_item(item["id"])


def test_preparation_keeps_short_dialogue_and_full_book_tail(library: LibraryEngine):
    pages = [[f"Story line {page * 30 + line:03d}" for line in range(30)] for page in range(4)]
    pages[0][0] = "不。"
    pages[-1][-1] = "THE FINAL ANSWER"
    item = add_pdf(library, pages)
    service = BookSourceService(library.workspace_root)

    source = service.prepare_source(item["id"])
    assert source["status"] == "ready"
    assert source["quality"]["pages_processed"] == 4
    assert source["quality"]["tail_covered"] is True
    assert source["segment_count"] > 100

    segments = []
    cursor = -1
    while True:
        result = service.list_segments(item["id"], source["source_version_id"], cursor, 25)
        segments.extend(result["segments"])
        if result["next_ordinal"] is None:
            break
        cursor = result["next_ordinal"]
    assert segments[0]["text"] == "不。"
    assert segments[-1]["text"] == "THE FINAL ANSWER"
    assert segments[-1]["page"] == 4

    locator = service.resolve_evidence(item["id"], source["source_version_id"], segments[-1]["id"])
    assert locator["quote"] == "THE FINAL ANSWER"
    assert locator["page"] == 4
    assert (library.workspace_root / locator["asset_path"]).is_file()


def test_library_delete_fences_source_before_removing_item(library: LibraryEngine):
    item = add_pdf(library, [["A short story", "The end"]])
    service = BookSourceService(library.workspace_root)
    source = service.prepare_source(item["id"])

    assert library.delete_item(item["id"]) is True
    with pytest.raises(ValueError, match="not found"):
        library.get_item(item["id"])
    with pytest.raises(BookWorldError, match="unavailable") as failure:
        service.list_segments(item["id"], source["source_version_id"])
    assert failure.value.code == "source_removed"


def test_repeated_prepare_reuses_identity_and_detects_snapshot_corruption(library: LibraryEngine):
    item = add_pdf(library, [["A short story", "The end"]])
    service = BookSourceService(library.workspace_root)
    first = service.prepare_source(item["id"])
    again = service.prepare_source(item["id"])
    assert again["book_id"] == first["book_id"]
    assert again["source_version_id"] == first["source_version_id"]
    segment = service.list_segments(item["id"], first["source_version_id"])["segments"][0]
    locator = service.resolve_evidence(item["id"], first["source_version_id"], segment["id"])
    (library.workspace_root / locator["asset_path"]).write_bytes(b"corrupt snapshot")
    with pytest.raises(BookWorldError) as failure:
        service.prepare_source(item["id"])
    assert failure.value.code == "source_changed"


def test_image_only_pdf_reports_ocr_requirement(library: LibraryEngine):
    item = add_pdf(library, [[]])
    path = library.workspace_root / item["library_path"] / "main.pdf"
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    image.clear_with(255)
    with fitz.open() as document:
        page = document.new_page()
        page.insert_image(fitz.Rect(40, 40, 100, 100), stream=image.tobytes("png"))
        document.save(path)
    library.db.execute(
        "UPDATE library_items SET pdf_sha256=? WHERE id=?",
        (library._compute_sha256(path), item["id"]),
    )
    library.db.commit()
    source = BookSourceService(library.workspace_root).prepare_source(item["id"])
    assert source["status"] == "needs_ocr"
    assert source["quality"]["image_only_pages"] == [1]
    assert source["segment_count"] == 0


def test_source_scope_rejects_other_book_and_keeps_original_pdf(library: LibraryEngine):
    first_item = add_pdf(library, [["First novel", "A secret"]])
    second_item = add_pdf(library, [["Second novel", "Different secret"]])
    service = BookSourceService(library.workspace_root)
    first = service.prepare_source(first_item["id"])
    second = service.prepare_source(second_item["id"])
    assert first["book_id"] != second["book_id"]
    with pytest.raises(BookWorldError) as failure:
        service.list_segments(second_item["id"], first["source_version_id"])
    assert failure.value.code == "source_removed"

    main_pdf = library.workspace_root / first_item["library_path"] / "main.pdf"
    main_pdf.write_bytes(b"attachment replaced later")
    segment = service.list_segments(first_item["id"], first["source_version_id"])["segments"][1]
    locator = service.resolve_evidence(first_item["id"], first["source_version_id"], segment["id"])
    assert locator["quote"] == "A secret"
    assert (library.workspace_root / locator["asset_path"]).read_bytes() != main_pdf.read_bytes()


def test_unready_attachment_has_explicit_state(library: LibraryEngine):
    item = library.create_item(metadata={"title": "Waiting for PDF"})
    service = BookSourceService(library.workspace_root)
    assert service.get_source(item["id"])["status"] == "not_prepared"
    with pytest.raises(BookWorldError) as failure:
        service.prepare_source(item["id"])
    assert failure.value.code == "source_not_ready"


@pytest.mark.parametrize("limit,cursor", [(0, -1), (201, -1), (True, -1), (25, -2), (25, True)])
def test_bad_segment_pagination_is_rejected(library: LibraryEngine, limit, cursor):
    service = BookSourceService(library.workspace_root)
    with pytest.raises(BookWorldError) as failure:
        service.list_segments(1, "not-a-version", cursor, limit)
    assert failure.value.code == "invalid_request"


def test_repeated_migrations_preserve_legacy_items_and_enable_foreign_keys(library: LibraryEngine):
    from backend.services.knowledge_migrations import MigrationRunner

    item = add_pdf(library, [["A complete story"]])
    service = BookSourceService(library.workspace_root)
    source = service.prepare_source(item["id"])
    run_knowledge_index_migrations(library.db_path)
    assert service.get_source(item["id"])["source_version_id"] == source["source_version_id"]
    assert library.get_item(item["id"])["title"] == "Original test novel"
    observed = []
    runner = MigrationRunner(library.db_path)
    runner.register(
        9999,
        "test_foreign_keys",
        lambda db: observed.append(db.execute("PRAGMA foreign_keys").fetchone()[0]),
    )
    runner.run()
    assert observed == [1]
