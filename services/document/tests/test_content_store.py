"""Bản thô đi vào và ra khỏi Mongo mà không đổi hình dạng.

Không test nào ở đây cần Mongo chạy. Nhưng chiều đi-về phải đi qua **BSON thật**
(`bson.encode` / `bson.decode` của chính `pymongo` đã cài), không chỉ qua `as_document` rồi
`from_document`: bản đầu của file này làm vậy, và review Task 1 (11/10/2026) chứng minh nó xanh cả
khi một mốc thời gian đi vào Mongo rồi đi ra **khác** đi -- BSON chỉ giữ tới mili giây.
"""

from datetime import UTC, datetime, timedelta, timezone

import bson
import pytest
from bson.codec_options import CodecOptions
from pymongo.errors import AutoReconnect

from contracts import RawBlock, RawDocument, RawPage, RawSource, page_key
from document.content_store import (
    ContentStore,
    ContentStoreUnavailable,
    as_document,
    finished,
    from_document,
)

# Có micro giây lẻ, có cả múi giờ +07:00: đúng hai thứ BSON xử khác Python.
_AT = datetime(2026, 10, 11, 16, 30, 3, 456789, tzinfo=timezone(timedelta(hours=7)))


def _through_mongo(body: dict) -> dict:
    """Đi một vòng qua BSON như một lần ghi rồi đọc thật, với `tz_aware=True` như `ContentStore`."""
    return bson.decode(bson.encode(body), codec_options=CodecOptions(tz_aware=True))


def _page(page: int = 3, at: datetime = _AT) -> RawPage:
    return RawPage(
        document_id="doc-1",
        page=page,
        source=RawSource.OCR,
        width=1140,
        height=1600,
        blocks=(
            RawBlock(kind="paragraph_title", box=(10, 20, 300, 60), text="KHÁI NIỆM"),
            RawBlock(kind="formula", box=(10, 80, 300, 120), text="a : b = c"),
        ),
        text="KHÁI NIỆM a : b = c",
        seconds={"layout": 1.8, "recognize": 1.7},
        read_at=at,
    )


def test_a_page_is_keyed_so_writing_it_again_overwrites() -> None:
    """arq chạy lại một lô thì trang ấy được ghi lần hai -- cùng `_id` nên ghi đè, không nhân đôi.

    Khoá dựng bằng `contracts.page_key`, không bằng một f-string riêng: bên đọc ở plan 3c phải dựng
    đúng khoá ấy để lấy một trang.
    """
    assert as_document(_page(3))["_id"] == page_key("doc-1", 3) == "doc-1:3"
    assert as_document(_page(3))["_id"] != as_document(_page(4))["_id"]


def test_a_page_comes_back_out_of_bson_exactly_as_it_was_stored() -> None:
    """Mongo là nơi lưu, không phải nơi định nghĩa: đọc ra phải dựng lại đúng thứ đã ghi.

    So **thứ ta gửi đi** với **thứ ta đọc về**, không so với một giá trị cắt sẵn: bản đầu của test
    này so với giá trị cắt sẵn, và bỏ hẳn bước cắt trong `as_document` vẫn xanh -- BSON tự cắt, nên
    bước của ta vô hình. Tuple (`box`, `blocks`) ra thành list rồi pydantic dựng lại thành tuple;
    múi giờ +07:00 ra thành UTC nhưng vẫn là cùng một khoảnh khắc.
    """
    sent = as_document(_page())
    assert from_document(RawPage, _through_mongo(sent)) == from_document(RawPage, sent)
    assert sent["read_at"].microsecond == 456000


def test_a_time_without_a_timezone_is_refused() -> None:
    """Mongo coi giờ không múi là UTC: `datetime.now()` giờ Việt Nam sẽ lệch bảy tiếng, im lặng."""
    with pytest.raises(ValueError, match="read_at"):
        as_document(_page(at=datetime(2026, 10, 11, 16, 30)))


def test_the_source_is_stored_as_a_bare_string() -> None:
    """Bên đọc của plan 3c có thể không dùng Python, nên giá trị phải là chuỗi trần."""
    body = as_document(_page())
    assert body["source"] == "ocr"
    assert type(body["source"]) is str


def test_a_document_header_is_keyed_by_the_document_id() -> None:
    """Cùng id với hàng `documents` trong kho của BE: hai kho nói về một tài liệu bằng một khoá."""
    header = RawDocument(
        document_id="doc-1", source=RawSource.TEXT_LAYER, page_count=29, started_at=_AT
    )
    body = as_document(header)
    assert body["_id"] == "doc-1"
    assert body["finished_at"] is None
    back = from_document(RawDocument, _through_mongo(body))
    assert back == header.model_copy(update={"started_at": _AT.replace(microsecond=456000)})
    assert back.started_at.tzinfo is not None
    assert back.started_at.astimezone(UTC) == _AT.replace(microsecond=456000).astimezone(UTC)


def test_finishing_follows_the_same_time_rule_as_writing() -> None:
    """`finish` ghi một mốc thời gian không qua `as_document`, nên nó phải tự theo cùng luật: cắt
    tới mili giây, từ chối giờ không múi. Thử tay ngày 11/10/2026 bắt được nó lọt luật này.
    """
    update = finished(_AT)
    assert update["$set"]["finished_at"].microsecond == 456000
    with pytest.raises(ValueError, match="finished_at"):
        finished(datetime(2026, 10, 11, 16, 30))


@pytest.mark.asyncio
async def test_a_mongo_error_becomes_the_typed_error() -> None:
    """Lỗi của `pymongo` thành `ContentStoreUnavailable`, để `handlers` xin arq chạy lại mà không
    phải import `pymongo` -- và không phải `except Exception`, thứ nuốt cả lỗi lập trình.
    """

    class _Down:
        async def replace_one(self, *_: object, **__: object) -> None:
            raise AutoReconnect("connection reset")

    store = ContentStore("mongodb://127.0.0.1:1", "unused")
    store._db = {"pages": _Down()}
    with pytest.raises(ContentStoreUnavailable, match="doc-1"):
        await store.put_page(_page())
    await store.close()
