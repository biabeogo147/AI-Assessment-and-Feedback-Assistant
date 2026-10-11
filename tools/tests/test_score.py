"""Thước đo phải đo đúng thứ nó hứa đo, và phải phân biệt được hai loại hỏng khác nhau.

Mỗi test ở đây ghim **một** quyết định của `score.py`. Đọc chúng theo thứ tự là đọc lý do bộ đo
có hình dạng này chứ không phải một hình dạng khác.
"""

import pytest

from ocr_bench.score import (
    align,
    cer,
    diacritic_error_rate,
    has_mark,
    label_accuracy,
    latex_distance,
    latex_matches,
    levenshtein,
    match_blocks,
    missing_words,
    normalise_latex,
    order_inversions,
    wer,
    without_marks,
)

# Đúng chuỗi mà PaddleOCR làm hỏng, đo ngày 10/10/2026 ở mức byte: nó phát ra được ă ũ ồ ư ê ô ơ
# đ nhưng không bao giờ phát ra tổ hợp hai dấu, nên mọi ế ố ộ ớ ứ ợ rụng mất.
_TRUTH = "Kết nối tri thức với cuộc sống"
_PADDLE = "Kt ni tri thc vi cuc sng"


def test_levenshtein_counts_the_three_edits() -> None:
    """Chèn, xoá, thay -- mỗi cái một đơn vị, không cái nào đắt hơn cái nào."""
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "abd") == 1
    assert levenshtein("abc", "ab") == 1
    assert levenshtein("ab", "abc") == 1
    assert levenshtein("kitten", "sitting") == 3


def test_cer_is_blind_to_how_a_letter_is_encoded() -> None:
    """`ế` dựng sẵn và `ế` tổ hợp phải cho CER bằng 0.

    Không chuẩn hoá thì một engine đọc đúng hoàn toàn vẫn ăn một CER khác 0, và không ai nhìn ra
    vì trên màn hình hai chuỗi giống hệt nhau. Đây là lỗi đắt nhất một bộ đo chữ Việt có thể mắc.
    """
    assert cer("Kết", "Kết") == 0.0


def test_cer_may_pass_one_when_the_engine_invents_text() -> None:
    """Không chặn ở 1,0, có chủ ý.

    Một engine nhả ra gấp ba lượng chữ cần đọc tệ hơn một engine im lặng. Chặn ở 1,0 là nói hai
    ca ấy như nhau, và lúc ấy bảng điểm không còn phân biệt được chúng.
    """
    assert cer("abc", "") == 1.0
    assert cer("abc", "abcabcabc") == 2.0


def test_an_empty_label_only_forgives_an_empty_read() -> None:
    """Nhãn rỗng mà engine bịa chữ là một lỗi, không phải một phép chia cho không."""
    assert cer("", "") == 0.0
    assert cer("", "bịa ra") == 1.0


def test_without_marks_also_strips_the_stroke_on_d() -> None:
    """`đ` không mang dấu phụ tổ hợp, nên NFD không tách nó ra -- phải gỡ bằng tay.

    Thiếu dòng ấy thì một engine đọc `d` thay cho `đ` bị tính là lỗi **chữ** chứ không phải lỗi
    **dấu**, và phép đo sẽ chỉ sai ở đúng những trang nói về *đường thẳng* hay *điểm*.
    """
    assert without_marks("đường thẳng") == "duong thang"
    assert without_marks("Đồ thị") == "Do thi"


def test_alignment_pairs_a_dropped_character_with_nothing() -> None:
    """Phép dóng là nền của thước dấu, nên nó phải nói được ký tự nào **biến mất**."""
    assert align("abc", "abc") == [("a", "a"), ("b", "b"), ("c", "c")]
    assert align("abc", "ac") == [("a", "a"), ("b", None), ("c", "c")]
    assert align("ac", "abc") == [("a", "a"), (None, "b"), ("c", "c")]


def test_alignment_normalises_before_it_compares() -> None:
    """Quyết định số một của cả module -- chuẩn hoá NFC trước **mọi** phép so -- cũng áp ở đây.

    Không có test này thì bỏ `nfc()` khỏi `align` vẫn xanh, và lúc ấy thước lỗi dấu sai **im
    lặng** trên mọi nhãn viết bằng ký tự tổ hợp: `ế` tổ hợp dài ba code point, nên nó dóng thành
    ba cặp và ăn hai lỗi cho một ký tự đọc đúng. Review 10/10/2026 bắt được.
    """
    assert align("ế", "ế") == [("ế", "ế")]
    assert diacritic_error_rate("ế", "ế") == 0.0


def test_the_thumb_also_catches_a_mark_invented_out_of_nothing() -> None:
    """Bịa dấu lên chữ trần là lỗi kinh điển thứ hai của OCR tiếng Việt, cạnh lỗi rụng dấu.

    Bản đầu chỉ duyệt ký tự có dấu **của nhãn**, nên `"Toan hoc"` đọc thành `"Toán học"` ăn
    **0,0** ở đúng cái thước sinh ra để bắt lỗi dấu.
    """
    assert diacritic_error_rate("Toan hoc", "Toán học") == 1.0
    assert diacritic_error_rate("ban can bo", "bán cán bô") == 1.0


def test_cer_understates_a_total_loss_of_diacritics_and_this_thumb_does_not() -> None:
    """Đây là lý do thước này tồn tại, và nó dựng trên một phép đo thật.

    Một trang tiếng Việt có chừng một phần tư ký tự mang dấu, nên một engine đánh rơi **toàn bộ**
    dấu vẫn chỉ ăn CER cỡ 0,2 -- một con số trông như *"hơi kém"* trong khi chữ nó trả về không
    đọc được. Cặp assert dưới đây ghim đúng khoảng cách ấy.
    """
    stripped = "Ket noi tri thuc voi cuoc song"
    assert cer(_TRUTH, stripped) < 0.25
    assert diacritic_error_rate(_TRUTH, stripped) == 1.0


def test_the_paddle_hole_reads_as_a_total_loss() -> None:
    """Chuỗi thật PaddleOCR trả về, và nó phải ra 1,0.

    Nó cũng là ca đã bác bỏ bản đầu của thước này: bản ấy đo bằng **hiệu** của CER và
    CER-sau-khi-gỡ-dấu, với giả định rằng engine thủng từ điển sẽ nhả ra chữ trần. PaddleOCR
    **xoá hẳn** nguyên âm có dấu -- `Kết nối` ra `Kt ni`, không phải `Ket noi` -- nên gỡ dấu ở
    cả hai phía không làm chúng gần nhau, và hiệu ấy bằng 0 ở đúng ca nó sinh ra để bắt.
    """
    assert diacritic_error_rate(_TRUTH, _PADDLE) == 1.0


def test_a_perfect_read_and_a_text_without_marks_both_score_zero() -> None:
    """Không có gì hỏng, và không có gì để hỏng -- hai ca khác nhau, cùng một con số đúng."""
    assert diacritic_error_rate(_TRUTH, _TRUTH) == 0.0
    assert diacritic_error_rate("abc 123", "xyz 456") == 0.0


def test_one_wrong_mark_out_of_six_is_one_sixth() -> None:
    """Thước phải chia độ, không chỉ phân biệt 0 với 1.

    `_TRUTH` có đúng sáu ký tự mang dấu: ế ố ứ ớ ộ ố. Đọc sai đúng một cái ra 1/6.
    """
    assert sum(1 for one in _TRUTH if has_mark(one)) == 6
    assert diacritic_error_rate(_TRUTH, _TRUTH.replace("thức", "thưc")) == pytest.approx(1 / 6)


def test_wer_catches_what_cer_shrugs_at() -> None:
    """Một ký tự rụng giữa **mỗi** từ: CER rất thấp, WER gần 1,0.

    Cặp số ấy là cả lý do WER đi cạnh CER. Chỉ con số thứ hai nói rằng không câu nào còn đọc
    được, trong khi con số thứ nhất nói mọi thứ gần như ổn.
    """
    truth = "một hai ba bốn năm sáu bảy tám"
    read = "mt hi ba bn nm sá bả tm"
    assert cer(truth, read) < 0.35
    assert wer(truth, read) > 0.8


def test_normalise_latex_ignores_how_the_spacing_was_written() -> None:
    """`a+b` và `a + b` là cùng một công thức; phạt vì một dấu cách là đo cách viết."""
    assert normalise_latex("a + b") == normalise_latex("a+b")
    assert normalise_latex(r"27\;000") == normalise_latex("27 000")
    assert normalise_latex(r"\left(x\right)") == normalise_latex("(x)")
    assert normalise_latex(r"x \quad y") == "xy"


def test_latex_matches_still_sees_a_real_difference() -> None:
    """Chuẩn hoá không được xoá mất nội dung: `R` khác `P`.

    Đây đúng ca PP-FormulaNet đọc sai, đo ngày 10/10/2026 -- `P(x)=R(x)-C(x)` thành
    `P(x)=P(x)-C(x)`. Một bộ chuẩn hoá quá tay sẽ nuốt luôn lỗi ấy.
    """
    assert latex_matches("P(x)=R(x)-C(x)", "P(x) = R(x) - C(x)")
    assert not latex_matches("P(x)=R(x)-C(x)", "P(x)=P(x)-C(x)")


def test_latex_distance_tells_one_wrong_character_from_a_ruined_read() -> None:
    """Khớp-hay-không là một cánh cửa đóng, và bước sửa ở plan sau chỉ cứu được loại thứ nhất."""
    nearly = latex_distance("P(x)=R(x)-C(x)", "P(x)=P(x)-C(x)")
    ruined = latex_distance("P(x)=R(x)-C(x)", "lap-100=")
    assert 0.0 < nearly < 0.15
    assert ruined > 0.5


def test_label_accuracy_forgives_one_merge_instead_of_blaming_everything_after_it() -> None:
    """Engine gộp hai đoạn làm một thì **một** lỗi, không phải lệch pha cả trang.

    Một phép so theo vị trí sẽ báo gần như sai hết cho đúng một lỗi, và lúc ấy con số không còn
    nói được engine đoán nhãn tốt hay tệ.
    """
    truth = ["doc_title", "text", "text", "formula", "number"]
    merged = ["doc_title", "text", "formula", "number"]
    assert label_accuracy(truth, merged) == pytest.approx(0.8)
    assert label_accuracy(truth, truth) == 1.0


def test_label_accuracy_never_goes_below_zero() -> None:
    """Engine nhả ra mười nhãn cho một trang hai khối vẫn là 0,0, không phải một số âm."""
    assert label_accuracy(["text", "number"], ["text"] * 10) == 0.0


def test_match_blocks_pairs_a_half_read_block_with_its_original() -> None:
    """Một khối đọc đúng **thật sự một nửa** vẫn là khối ấy; một khối bịa ra thì không.

    Bản đầu của test này dùng một chuỗi chỉ rụng dấu -- giống nhau trên 0,9 -- nên nó mang tên
    *một nửa* mà đo một thứ khác, và hằng số ngưỡng 0,5 nâng lên 0,9 vẫn xanh. Review 10/10/2026
    bắt được. Chuỗi dưới đây sai đúng một nửa số ký tự.
    """
    truth = ["Gọi S là tập các hành tinh của Hệ Mặt Trời", "Tập hữu hạn và tập vô hạn"]
    read = ["Gọi S là tập các xxxx xxxx xxx xx xxx xxxx", "KẾT NỐI TRI THỨC VỚI CUỘC SỐNG"]
    assert match_blocks(truth, read) == [0, None]


def test_a_block_read_barely_worse_than_half_is_a_different_block() -> None:
    """Cặp với test trên, và hai cái kẹp hằng số ngưỡng giữa chúng.

    Đổi `_SAME_BLOCK_SIMILARITY` theo chiều nào thì một trong hai đỏ. Không có cặp này thì nâng
    ngưỡng từ 0,5 lên 0,9 chạy qua toàn bộ suite mà không gì kêu.
    """
    truth = ["abcdefghij"]
    assert match_blocks(truth, ["abcdefXXXX"]) == [0]
    assert match_blocks(truth, ["abcdXXXXXX"]) == [None]


def test_a_page_number_survives_one_stray_character() -> None:
    """Khối một hai ký tự: `'7'` và `'7.'` là cùng một số trang, `'7'` và `'9'` thì không.

    Luật tỉ lệ không nói được gì trên hai ký tự, nên khối ngắn có luật riêng. Nó không phải một
    tiện nghi: **cả 48 khối `number`** của bộ nhãn dài một tới hai ký tự, và chúng chính là thứ
    dùng để nối trang PDF với trang in trong sách.
    """
    assert match_blocks(["7"], ["7."]) == [0]
    assert match_blocks(["12"], ["12 "]) == [0]
    assert match_blocks(["7"], ["9"]) == [None]


def test_whitespace_is_not_a_reading_error() -> None:
    """Nhãn do ba người gõ, và họ căn cột bằng số khoảng trắng khác nhau.

    Đo ngày 10/10/2026: không gom khoảng trắng thì một engine đọc đúng tuyệt đối vẫn trả một CER
    sàn 0,34% ở lát A và 0,42% ở lát B -- gấp ba mươi lần lát C. Mọi so sánh giữa ba lát khi ấy
    là so cách gõ của ba người. Theo từng khối thì tệ hơn hẳn: `L6T1_p013` khối 5 có sàn 47%.
    """
    assert cer("a) 400;          b) 40;", "a) 400; b) 40;") == 0.0
    assert cer("một\nhai", "một hai") == 0.0
    assert wer("a b c", "a  b\nc") == 0.0


def test_wer_divides_by_the_label_not_by_what_the_engine_produced() -> None:
    """Mẫu số phải là nhãn. Engine nuốt nửa số từ thì nó ăn 0,5, không phải 1,0.

    Chia cho đầu ra của engine là để nó tự chấm mình trên chính phần nó chịu đọc -- và lúc ấy
    một engine im lặng một nửa trông giống hệt một engine đọc đủ. Đột biến đổi mẫu số sống sót
    qua cả suite trước review 10/10/2026.
    """
    assert wer("một hai ba bốn", "một hai") == 0.5
    assert wer("một hai", "một hai ba bốn") == 1.0


def test_match_blocks_gives_each_original_to_at_most_one_reader() -> None:
    """Hai khối engine đọc được không được cùng nối vào một khối nhãn vàng.

    Không chặn thì một engine nhả cùng một đoạn hai lần sẽ trông như đọc đúng cả hai.
    """
    truth = ["một đoạn văn dài để so sánh cho chắc"]
    read = ["một đoạn văn dài để so sánh cho chắc", "một đoạn văn dài để so sánh cho chắc"]
    assert match_blocks(truth, read) == [0, None]


def test_order_inversions_counts_pairs_not_displaced_blocks() -> None:
    """Thứ tự hoàn hảo là 0; một cặp đảo là 1; đảo ngược hoàn toàn ba khối là 3 cặp."""
    assert order_inversions([0, 1, 2, 3]) == 0
    assert order_inversions([0, 2, 1]) == 1
    assert order_inversions([2, 1, 0]) == 3


def test_order_inversions_ignores_blocks_that_matched_nothing() -> None:
    """Khối bịa ra đã bị `cer` và `label_accuracy` phạt rồi; phạt lần nữa ở đây là đếm hai lần.

    Con số này chỉ trả lời đúng một câu: những khối engine **có** đọc được, nó xếp đúng thứ tự
    không? Đó là câu quyết định bước dựng mục lục ở plan sau.
    """
    assert order_inversions([0, None, 1, None, 2]) == 0
    assert order_inversions([None, None]) == 0


def test_missing_words_ignores_order_because_an_llm_does() -> None:
    """Hai khung cạnh nhau đọc đan xen: không một chữ nào sai, nên không một từ nào thiếu.

    Đó là lý do thước này tồn tại cạnh CER -- CER của đúng ca này là một con số lớn.
    """
    truth = "khái niệm thuật ngữ kiến thức kĩ năng"
    read = "kiến thức kĩ năng khái niệm thuật ngữ"
    assert missing_words(truth, read) == 0.0
    assert cer(truth, read) > 0.5


def test_missing_words_keeps_the_marks() -> None:
    """`so` không phải `số`. Rụng dấu là đọc sai một từ, với người đọc và với LLM."""
    assert missing_words("số tự nhiên", "so tu nhien") == 1.0
    # Chỉ `tri` sống sót nguyên dạng: sáu trên bảy từ mất.
    assert missing_words(_TRUTH, _PADDLE) == pytest.approx(6 / 7)


def test_missing_words_counts_repeats() -> None:
    """Túi **có đếm**: nhãn có ba chữ `số`, bản đọc có hai, thì thiếu một trên bốn từ."""
    assert missing_words("số số số chia", "số số chia") == pytest.approx(1 / 4)


def test_missing_words_forgives_case_and_edge_punctuation() -> None:
    """`Nhau.` ở cuối câu và `nhau` giữa dòng là một từ; dấu câu không phải thứ đang được đo."""
    assert missing_words("Chia hết cho nhau.", "chia hết, cho nhau") == 0.0


def test_missing_words_on_an_empty_page() -> None:
    """Trang bìa không chữ: không có gì để thiếu, nên là 0 chứ không phải chia cho 0."""
    assert missing_words("", "rác") == 0.0
    assert missing_words("một hai", "") == 1.0
