"""TXT imports use the same source scopes and exact Unicode locators as PDF."""

import hashlib

import pytest

from backend.services.book_world import BookSourceService, BookWorldError


def add_text(library, text, encoding="utf-8"):
    uploaded = library.workspace_root / ("upload_" + encoding + ".txt")
    uploaded.write_bytes(text.encode(encoding))
    item = library.create_item(
        pdf_path=uploaded, metadata={"title": "文本小说", "item_type": "book"}
    )
    library.import_text_attachment(item["id"], uploaded)
    return library.get_item(item["id"])


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "gb18030"])
def test_import_txt_preserves_tail_and_original_unicode_span(book_library, encoding):
    original = (
        "第一回 初入山林\r\n\r\n不。\r\n"
        + "\r\n".join(f"人物甲回忆第{i}次相遇。" for i in range(120))
        + "\r\n最后一回 完结\r\n全书最后一句。"
    )
    item = add_text(book_library, original, encoding)
    assert item["pdf_sha256"] is None
    assert item["source_format"] == "txt"
    assert item["source_sha256"] == hashlib.sha256(original.encode(encoding)).hexdigest()
    service = BookSourceService(book_library.workspace_root)
    source = service.prepare_source(item["id"])
    assert source["status"] == "ready"
    assert source["format"] == "txt"
    assert source["segment_count"] > 100
    assert source["quality"]["tail_covered"] is True
    assert service.prepare_source(item["id"])["source_version_id"] == source["source_version_id"]
    rows = []
    cursor = -1
    while True:
        page = service.list_segments(item["id"], source["source_version_id"], cursor, 25)
        rows.extend(page["segments"])
        if page["next_ordinal"] is None:
            break
        cursor = page["next_ordinal"]
    assert rows[1]["text"] == "不。"
    assert rows[-1]["text"] == "全书最后一句。"
    locator = service.resolve_evidence(item["id"], source["source_version_id"], rows[-1]["id"])
    assert locator["page"] is None
    assert locator["format"] == "txt"
    assert original[locator["source_start"] : locator["source_end"]] == "全书最后一句。"
    context = service.read_source(
        item["id"], source["source_version_id"], locator["source_start"], 100
    )
    assert context["text"] == "全书最后一句。"
    assert context["next_offset"] is None


def test_txt_locator_counts_codepoints_instead_of_utf16_units(book_library):
    item = add_text(book_library, "第一章\n人物甲😀说：你好。\n结束。")
    service = BookSourceService(book_library.workspace_root)
    source = service.prepare_source(item["id"])
    row = service.list_segments(item["id"], source["source_version_id"])["segments"][1]
    locator = service.resolve_evidence(item["id"], source["source_version_id"], row["id"], 3, 4)
    assert locator["quote"] == "😀"
    assert locator["source_end"] - locator["source_start"] == 1


def test_binary_disguised_as_txt_is_rejected_before_attachment_publish(book_library):
    path = book_library.workspace_root / "binary.txt"
    path.write_bytes(b"MZ\x00\x01not a novel")
    item = book_library.create_item(pdf_path=path, metadata={"title": "Invalid"})
    with pytest.raises(ValueError):
        book_library.import_text_attachment(item["id"], path)
    assert book_library.get_item(item["id"])["attachments"] == []


def test_editing_book_metadata_keeps_txt_list_format(book_library):
    item = add_text(book_library, "第一章\n人物甲：你好。")
    book_library.update_metadata(item["id"], {"title": "Edited", "tags": ["小说"]})
    assert book_library.get_item(item["id"])["source_format"] == "txt"
    items, total = book_library.list_items()
    assert total == 1
    assert items[0]["source_format"] == "txt"


def test_txt_read_rejects_other_book_source(book_library):
    first = add_text(book_library, "第一本小说。")
    second = add_text(book_library, "第二本小说。")
    service = BookSourceService(book_library.workspace_root)
    version = service.prepare_source(first["id"])
    with pytest.raises(BookWorldError) as error:
        service.read_source(second["id"], version["source_version_id"])
    assert error.value.code == "source_removed"
