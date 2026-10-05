r"""Bộ khôi phục dấu gạch chéo, và những chỗ nó phải **không** động vào.

Mọi chuỗi trong file này là byte thật, đo từ database ngày 05/10/2026 bằng
`select encode(convert_to(stem,'UTF8'),'hex')`. Không có chuỗi nào được bịa ra cho hợp
với code: một test dựng từ trí tưởng tượng về hỏng hóc sẽ xanh trong khi hỏng hóc thật
đi qua.

Nửa sau của file quan trọng ngang nửa đầu. Việc này đi chữa một thứ bằng cách thay ký tự,
mà một bộ thay ký tự quá hăng sẽ phá đúng cái vừa sửa xong đợt trước -- xuống dòng trong
lời giải. Nên mỗi ca "phải giữ nguyên" ở đây là một hàng rào, không phải một test cho đủ.
"""

import pytest

from agent.latex_escapes import LATEX_COMMANDS, restore_latex_escapes


class TestNuotRoiDungLai:
    """Năm ca JSON có thể đẻ ra, mỗi ca một lệnh có thật."""

    @pytest.mark.parametrize(
        ("broken", "whole"),
        [
            # Ba ca đo được trong database, nguyên văn.
            ("$\x0crac{1}{2}$", "$\\frac{1}{2}$"),
            ("$I = \x09imes 2$", "$I = \\times 2$"),
            ("$\x08igg|x\x08igg|$", "$\\bigg|x\\bigg|$"),
            # Hai ca còn lại của bảng escape, chưa gặp nhưng cùng một cơ chế.
            ("$\x0aabla f$", "$\\nabla f$"),
            ("$x \x0dightarrow 0$", "$x \\rightarrow 0$"),
        ],
    )
    def test_dung_lai_lenh_bi_nuot(self, broken: str, whole: str) -> None:
        """Ký tự điều khiển cộng phần đuôi thành một lệnh thì được trả lại dấu gạch chéo."""
        assert restore_latex_escapes(broken) == whole

    def test_cau_that_trong_database(self) -> None:
        """Nguyên một đề bài đã hỏng, dựng lại đủ cả ba lệnh trong đó."""
        broken = (
            "Tính giá trị của tích phân sau: "
            "$I = \x0crac{1}{2} \x09imes \x08igg| \x0crac{1}{3} "
            "\\int_0^1 (3x^2 - 2x + 1)\\,dx \\bigg|$"
        )
        whole = (
            "Tính giá trị của tích phân sau: "
            "$I = \\frac{1}{2} \\times \\bigg| \\frac{1}{3} "
            "\\int_0^1 (3x^2 - 2x + 1)\\,dx \\bigg|$"
        )
        assert restore_latex_escapes(broken) == whole

    def test_lenh_dai_an_het_phan_duoi_cua_no(self) -> None:
        """`\\tfrac` nguyên vẹn, không phải `\\t` rồi bỏ lại `frac` dính vào công thức.

        Thứ loại được bản ngắn ở đây là **luật ranh giới**, không phải chiều của vòng
        lặp: `t` đứng trước `f`, mà `f` là chữ cái, nên `t` không qua được ranh giới. Đã
        đo bằng đột biến -- đảo chiều vòng lặp không làm test nào đỏ.
        """
        assert restore_latex_escapes("$\x09frac{1}{2}$") == "$\\tfrac{1}{2}$"


class TestKhongDuocDongVao:
    """Những chỗ ký tự điều khiển mang nghĩa thật."""

    def test_xuong_dong_trong_loi_giai_giu_nguyen(self) -> None:
        """Lời giải đánh số phải đi qua không suy suyển.

        Đây là thứ vừa được sửa cho hiển thị đúng đợt trước (`white-space: pre-wrap`).
        Một phép thay mù sẽ phá đúng nó.
        """
        body = "1. Tính nguyên hàm.\n2. Thay cận.\n3. Trừ hai giá trị."
        assert restore_latex_escapes(body) == body

    @pytest.mark.parametrize(
        "body",
        [
            # `\n` + `e` ghép thành `\ne`, và sau nó là dấu cách -- qua được luật ranh
            # giới. Chỉ luật độ dài tối thiểu mới cứu được câu này.
            "Bước 2\ne là cơ số của logarit tự nhiên",
            # `\r` + `m` ghép thành `\rm`, cùng cơ chế.
            "Khối lượng\rm là đại lượng vô hướng",
            # `\n` + `i` ghép thành `\ni`.
            "Xét\ni là đơn vị ảo",
        ],
    )
    def test_xuong_dong_truoc_lenh_hai_chu_giu_nguyen(self, body: str) -> None:
        """Lệnh hai chữ cái không đủ để kết tội một lần xuống dòng.

        Ba câu này đều **qua được** luật ranh giới -- `ne`, `rm`, `ni` đều là lệnh thật
        và đều có dấu cách ngay sau. Nếu không có `_MIN_LENGTH_AFTER_NEWLINE` thì cả ba
        bị biến thành công thức, và một lời giải xuống dòng bình thường vỡ ra.
        """
        assert restore_latex_escapes(body) == body

    def test_chu_tieng_viet_sau_ky_tu_hong_giu_nguyen(self) -> None:
        """`rac` không đứng một mình thành lệnh thì không ai được chạm vào nó."""
        assert restore_latex_escapes("\x0cracmot") == "\x0cracmot"

    def test_lenh_phai_ket_thuc_o_ranh_gioi(self) -> None:
        """`fracture` không phải `\\frac` + `ture`."""
        assert restore_latex_escapes("\x0cracture") == "\x0cracture"

    def test_chuoi_sach_di_qua_khong_doi(self) -> None:
        """Dữ liệu đúng không được bộ chữa làm cho khác đi."""
        whole = "$I = \\frac{1}{2} \\times \\int_0^1 x\\,dx$"
        assert restore_latex_escapes(whole) == whole

    def test_chuoi_rong(self) -> None:
        """Không có gì thì không có gì."""
        assert restore_latex_escapes("") == ""


class TestTuDien:
    """Từ điển là thứ quyết định, nên nó phải nói đúng về chính nó."""

    def test_chi_chua_lenh_bat_dau_bang_nam_chu_cai_bi_nuot(self) -> None:
        """Lệnh bắt đầu bằng chữ khác không bao giờ đi qua đây.

        `\\int`, `\\sum`, `\\alpha` sống sót nguyên vẹn qua JSON vì `\\i`, `\\s`, `\\a`
        không nằm trong tám escape hợp lệ. Để chúng vào từ điển là mời một lần nhận nhầm
        mà không mua lại được gì.
        """
        assert all(name[0] in "bfnrt" for name in LATEX_COMMANDS)


class TestDoDuocTrenLuotSoanThat:
    """Hai ca ra từ lượt soạn đầu tiên sau khi việc này xong, 06/10/2026.

    Một ca là lỗ hổng của từ điển, một ca là hành vi đúng của nó. Giữ cả hai vì chúng
    nói hai điều khác nhau, và cả hai đều là dữ liệu thật chứ không phải ca bịa.
    """

    def test_textstyle_tung_bi_bo_sot(self) -> None:
        r"""`\\textstyle` là lệnh thật, và bản đầu của từ điển không có nó.

        `text` có trong từ điển, nhưng luật ranh giới loại nó đi vì sau `text` là chữ
        `s`. Nên cả cụm ở lại nguyên -- đúng hướng hỏng mong muốn, nhưng vẫn là một
        câu không dựng hình được trước mặt giáo viên.
        """
        assert restore_latex_escapes("$\x09extstyle x$") == r"$\textstyle x$"

    def test_lenh_khong_co_that_thi_de_nguyen(self) -> None:
        r"""Model viết `\\bigint`, thứ không tồn tại trong LaTeX.

        `big` có trong từ điển nhưng sau nó là chữ `i`, nên luật ranh giới loại. Và
        **nên** loại: KaTeX cũng không dựng được `\\bigint`, nên đoán ra một lệnh ở đây
        chỉ đổi một lỗi nhìn thấy được thành một lỗi ẩn.
        """
        broken = "$J = \x08igint_0^1 x\\,dx$"
        assert restore_latex_escapes(broken) == broken
