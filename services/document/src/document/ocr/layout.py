"""PP-DocLayout: một ảnh trang thành các khối có nhãn, hộp bao và **thứ tự đọc**.

Hai việc model không làm, và cả hai đo được trên trang 18 của Lớp 6 tập 1 ngày 10/10/2026:

1. **Nó trả về hộp sắp theo điểm tin cậy, không theo thứ tự đọc.** Khối đầu danh sách là khối
   model chắc nhất, không phải khối trên cùng trang. Thứ tự đọc là thứ bước dựng mục lục
   (`document-agent-hierarchy`) dựa vào, nên nó phải được dựng ở đây chứ không để người gọi tự
   đoán.
2. **Nó trả về hộp trùng nhau mang nhãn khác nhau.** Đúng hình chữ nhật `[322, 1130, 777, 1164]`
   ra **hai** lần: một `text` điểm 0,63 và một `formula` điểm 0,56. Giữ cả hai là đếm một khối
   hai lần -- chữ của nó vào bảng điểm hai lượt, và `order_inversions` thì đếm một cặp nghịch
   thế không có thật.

Model tải về `~/.paddlex/official_models/` ở lần chạy đầu. `on_startup` của worker phải nạp sẵn:
một job đi tải 200 MB giữa chừng là một job hết hạn, và nó hết hạn theo cách trông như một tệp
hỏng.
"""

import logging
from typing import Any

from paddleocr import LayoutDetection

from document.ocr.model import BBox, PageBlock, kind_from_label

logger = logging.getLogger(__name__)

# Dưới mức này thì bỏ.
#
# Bản đầu lấy **0,60**, đo trên đúng một trang. Review 10/10/2026 chạy lại trên mười trang và con
# số ấy sai theo chiều đắt nhất: nó cắt mất **chữ thật** và **không chặn được một khối rác nào**.
# Ba ca đo được -- chữ *"Giải"* ở p040 (0,550), *"Vì 18 ⋮ 6 nên ta có"* ở p046 (0,521), và dòng
# `24 = 2 · 2 · 2 · 3 = 2³ · 3;` ở p046 biến mất hẳn vì model chia đôi điểm của nó giữa hai nhãn
# (`text` 0,595 và `formula` 0,573) nên **cả hai nửa** đều dưới ngưỡng. Ở 0,50 thì ba khối ấy trở
# lại và mọi hộp mới nằm gọn trong một khối điểm cao hơn, tức phép gỡ trùng lo nốt phần còn lại.
_MIN_SCORE = 0.50

# Hai hộp phủ nhau từ ngần này trở lên **theo cả hai chiều** thì chúng là một khối, và cái điểm
# thấp hơn bị bỏ.
#
# Phải là cả hai chiều. Bản đầu chỉ hỏi *"A có nằm trong B không"*, và một hộp **con** luôn cho
# 1,0 -- nên nó đánh đồng *lồng nhau* với *trùng nhau*. Đo trên p041 và p046: một khối `formula`
# nằm trọn trong khối `text` của câu chứa nó bị xoá, và lúc ấy công thức bị hạ cấp thành chữ.
# Mất im lặng. Từ 11/10/2026 công thức không được đọc ở đây nữa, nhưng luật vẫn đúng: khối
# `FORMULA` là gợi ý *trang này có toán* cho bước đọc công thức lúc ra đề.
_COVERED = 0.70

# Khe trắng hẹp hơn ngần này điểm ảnh không được coi là một đường cắt.
#
# Việc thật của nó là **quyết khi nào bỏ cuộc**: dưới ngưỡng thì XY-cut tụt về phép sắp theo mép
# trên. Nó *không* ngăn việc cắt giữa một đoạn văn -- bản đầu của comment này nói thế và nói sai:
# `_widest_gap` chạy trên hộp **khối**, mà PP-DocLayout đã gộp các dòng của một đoạn vào một hộp,
# nên không có chỗ nào giữa đoạn để cắt. Kiểm trên mười trang: khe hẹp nhất được nhận là 12 và 13
# điểm ảnh, cả hai đều đúng chỗ.
_MIN_GAP = 12

# Quá ngần này hộp thì thôi đệ quy. Mỗi vết cắt có thể chỉ bóc ra một hộp, nên độ sâu là O(n) và
# Python hết ngăn xếp ở khoảng một nghìn hộp -- dựng lại được bằng 1 200 hộp xếp bậc thang. Một
# trang sách thật dưới 40 khối, nên cái chốt này không bao giờ chạy trên dữ liệu thật; nó có mặt
# để một trang nhiễu làm hỏng một trang chứ không giết cả lượt đọc một cuốn sách.
_TOO_MANY_BOXES = 400

# Đồ nội thất của trang: chúng không thuộc **cột** nào, nên chúng phải ra khỏi phép cắt trước khi
# đệ quy bắt đầu. Không tách thì số trang có thể lọt vào giữa: đo trên p041, một vết cắt dọc chia
# nửa dưới trang làm trái/phải và số trang nằm ở nửa trái, nên nó ra **trước** một sơ đồ ở nửa
# phải. Người đọc không bao giờ đọc số trang ở giữa trang.
_FURNITURE_FIRST = ("header",)
_FURNITURE_LAST = ("number", "footer")


class LayoutReader:
    """Giữ model PP-DocLayout đã nạp.

    Nạp một lần rồi dùng nhiều lần: nạp mất khoảng 2 giây, và một cuốn sách có hàng trăm trang.

    Attributes:
        _model: Predictor của PaddleOCR.
        _min_score: Ngưỡng điểm tin cậy.
    """

    def __init__(
        self,
        use_mkldnn: bool = False,
        min_score: float = _MIN_SCORE,
        model: str = "PP-DocLayout_plus-L",
        threads: int = 4,
    ):
        """Nạp model.

        Args:
            model: Tên model. `plus-L` là bản lớn nhất, và đó là chủ ý: đo 11/10/2026, bản `-M`
                và `-S` nhanh hơn 2 tới 9 lần nhưng gần như **không tìm ra khối công thức nào**.
                Công thức không còn được đọc lúc upload, nhưng nhãn `formula` vẫn là gợi ý *trang
                này có toán* cho bước đọc công thức lúc ra đề.
            threads: Số luồng CPU. Xem `page.PageReader`.
            use_mkldnn: Bật oneDNN. Mặc định **tắt**, vì trên Windows nó làm PaddlePaddle chết
                bằng `ConvertPirAttribute2RuntimeAttribute not support` ngay lời predict đầu
                tiên (đo 10/10/2026). Trên Linux nó chạy và nhanh hơn nhiều, nên đây là một công
                tắc chứ không phải một hằng số.
            min_score: Ngưỡng điểm tin cậy.
        """
        self._model = LayoutDetection(
            model_name=model, enable_mkldnn=use_mkldnn, cpu_threads=threads
        )
        self._min_score = min_score

    def read(self, image_path: str) -> list[PageBlock]:
        """Tìm các khối trên một ảnh trang.

        Args:
            image_path: Đường dẫn tới tệp ảnh.

        Returns:
            Các khối theo **thứ tự đọc**, chữ còn rỗng -- chặng này chỉ nói *ở đâu* và *là gì*.
            Danh sách rỗng là một kết quả hợp lệ: một trang trắng hay một trang nhiễu không có
            khối nào, và người gọi phải đi tiếp được chứ không được vấp.
        """
        boxes: list[dict[str, Any]] = []
        for one in self._model.predict(image_path):
            boxes.extend(one.json["res"].get("boxes", []))
        return blocks_from_boxes(boxes, self._min_score)


def blocks_from_boxes(
    boxes: list[dict[str, Any]], min_score: float = _MIN_SCORE
) -> list[PageBlock]:
    """Lọc, gỡ trùng và sắp thứ tự đọc cho đầu ra thô của model.

    Tách khỏi `LayoutReader.read` để lưới chạm được: phần này **thuần**, còn phần kia cần một
    model 200 MB và bốn giây mỗi trang. Mọi luật đáng canh đều nằm ở đây.

    Args:
        boxes: Các phần tử `boxes` model trả về, mỗi cái có `label`, `coordinate`, `score`.
        min_score: Ngưỡng điểm tin cậy.

    Returns:
        Các khối theo thứ tự đọc, chữ còn rỗng.
    """
    kept = _drop_duplicates(
        sorted(
            (box for box in boxes if box.get("score", 0.0) >= min_score),
            key=lambda box: box.get("score", 0.0),
            reverse=True,
        )
    )
    logger.info("layout found %s boxes, kept %s", len(boxes), len(kept))
    return [
        PageBlock(kind=kind_from_label(box["label"]), box=_box(box), text="")
        for box in in_reading_order(kept)
    ]


def _box(raw: dict[str, Any]) -> BBox:
    """Đổi toạ độ model trả về thành `BBox`.

    Args:
        raw: Một phần tử của `boxes`.

    Returns:
        Hộp bao, toạ độ làm tròn xuống số nguyên điểm ảnh.
    """
    left, top, right, bottom = (int(value) for value in raw["coordinate"])
    return BBox(left, top, right, bottom)


def _drop_duplicates(by_score: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bỏ hộp gần trùng khít với một hộp điểm cao hơn.

    *Gần trùng khít*, không phải *nằm trong*. Một khối `formula` nằm trọn trong khối `text` của
    câu chứa nó là quan hệ cha-con, và cả hai đều có việc riêng ở chặng sau.

    Args:
        by_score: Các hộp, **đã sắp giảm dần theo điểm**.

    Returns:
        Các hộp còn lại, vẫn theo thứ tự điểm.
    """
    kept: list[dict[str, Any]] = []
    for box in by_score:
        here = _box(box)
        if any(_same_place(here, _box(other)) >= _COVERED for other in kept):
            continue
        kept.append(box)
    return kept


def _same_place(one: BBox, other: BBox) -> float:
    """Hai hộp chiếm cùng một chỗ tới đâu.

    Lấy **phần phủ nhỏ hơn** trong hai chiều. Hai hộp trùng khít cho 1,0; một hộp con nằm trọn
    trong một hộp to cho một con số nhỏ, vì phía hộp to thì phần bị phủ ít. Đó chính là chỗ phân
    biệt *trùng lặp* với *lồng nhau*, và bản đầu không có nó.

    Args:
        one: Hộp thứ nhất.
        other: Hộp thứ hai.

    Returns:
        Một số từ 0,0 tới 1,0.
    """
    return min(_covered(one, other), _covered(other, one))


def _covered(inner: BBox, outer: BBox) -> float:
    """Phần diện tích của `inner` nằm trong `outer`.

    Args:
        inner: Hộp đang xét.
        outer: Hộp đã giữ.

    Returns:
        Một số từ 0,0 tới 1,0. `0,0` khi `inner` suy biến -- model trả về được một hộp dẹt, và
        chia cho diện tích 0 ở đây sẽ giết cả trang vì một khối.
    """
    area = inner.width * inner.height
    if area <= 0:
        return 0.0
    wide = max(0, min(inner.right, outer.right) - max(inner.left, outer.left))
    tall = max(0, min(inner.bottom, outer.bottom) - max(inner.top, outer.top))
    return wide * tall / area


def in_reading_order(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sắp các hộp theo thứ tự một người đọc chúng, bằng **XY-cut**.

    Mỗi bước: tìm khe trắng rộng nhất theo cả hai chiều, cắt theo chiều có khe rộng hơn, rồi lặp
    trên từng nửa. Cắt dọc thì nửa trái đi trước, cắt ngang thì nửa trên đi trước.

    Vì sao không phải một phép sắp theo mép trên, và vì sao không phải phép gom hàng: cả hai đọc
    **đan xen** hai cột cạnh nhau. Đo trên trang 18 của Lớp 6 tập 1 -- hai hộp *KHÁI NIỆM* và
    *KIẾN THỨC* đặt cạnh nhau -- phép gom hàng trả về dòng trái, dòng phải, dòng trái, dòng
    phải, trong khi người đọc hết hộp trái rồi mới sang hộp phải. Hình dạng ấy mở đầu **mọi** bài
    trong sách, nên nó không phải một ca hiếm.

    XY-cut chọn đúng ở đó vì nó so hai khe với nhau: trong vùng hai hộp, khe dọc giữa hai cột là
    66 điểm ảnh còn khe ngang rộng nhất giữa hai dòng là 19, nên nó cắt dọc. Ở vùng một cột chạy
    dọc thì ngược lại, và cùng một luật cho ra thứ tự đúng.

    **Đồ nội thất của trang ra trước.** Dòng chạy đầu trang đi đầu, số trang và dòng chạy cuối
    trang đi cuối, và chúng không tham gia phép cắt nào. Chúng không thuộc một cột nào, nên để
    chúng trong phép đệ quy là để số trang lọt vào giữa -- đo trên p041, nơi một vết cắt dọc chia
    nửa dưới trang làm trái/phải và số trang ở nửa trái ra **trước** một sơ đồ ở nửa phải.

    Args:
        boxes: Các hộp, thứ tự nào cũng được.

    Returns:
        Các hộp theo thứ tự đọc.
    """
    before = [box for box in boxes if box.get("label") in _FURNITURE_FIRST]
    after = [box for box in boxes if box.get("label") in _FURNITURE_LAST]
    body = [box for box in boxes if box not in before and box not in after]
    if before or after:
        return before + _cut(body) + after
    return _cut(body)


def _cut(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Phần đệ quy của XY-cut, trên thân trang đã bỏ đồ nội thất.

    Args:
        boxes: Các hộp thân trang.

    Returns:
        Các hộp theo thứ tự đọc.
    """
    if len(boxes) <= 1:
        return list(boxes)

    if len(boxes) > _TOO_MANY_BOXES:
        logger.warning("%s boxes on one page, falling back to a plain sort", len(boxes))
        return sorted(boxes, key=lambda box: (_box(box).top, _box(box).left))

    across, at_x = _widest_gap(boxes, vertical=True)
    down, at_y = _widest_gap(boxes, vertical=False)

    if max(across, down) < _MIN_GAP:
        # Không có khe nào đáng tin -- các hộp chồng lấn nhau. Sắp theo mép trên rồi mép trái là
        # phép lùi an toàn: nó không bao giờ đúng hơn XY-cut, nhưng nó luôn kết thúc.
        return sorted(boxes, key=lambda box: (_box(box).top, _box(box).left))

    if across >= down:
        first = [box for box in boxes if _box(box).left < at_x]
        second = [box for box in boxes if _box(box).left >= at_x]
    else:
        first = [box for box in boxes if _box(box).top < at_y]
        second = [box for box in boxes if _box(box).top >= at_y]

    # Không có chốt `if not first or not second` ở đây, và sự vắng mặt ấy là có chủ ý: một vết
    # cắt chỉ được nhận khi khe rộng ít nhất `_MIN_GAP > 0`, tức luôn có ít nhất một hộp mỗi
    # phía. Review 10/10/2026 chứng minh nhánh ấy là code chết và xoá nó đi thì lưới vẫn xanh --
    # tức nó cũng không canh được gì.
    return _cut(first) + _cut(second)


def _widest_gap(boxes: list[dict[str, Any]], vertical: bool) -> tuple[int, int]:
    """Tìm khe trắng rộng nhất, và chỗ cắt.

    Args:
        boxes: Các hộp.
        vertical: True thì tìm khe **dọc** (chiếu lên trục x), False thì khe ngang.

    Returns:
        Cặp (độ rộng khe, toạ độ bắt đầu nửa sau). Khe `0` nghĩa là không có chỗ nào cắt được.
    """
    spans = sorted(
        (_box(box).left, _box(box).right) if vertical else (_box(box).top, _box(box).bottom)
        for box in boxes
    )
    widest, at = 0, 0
    reach = spans[0][1]
    for start, end in spans[1:]:
        if start - reach > widest:
            widest, at = start - reach, start
        reach = max(reach, end)
    return widest, at
