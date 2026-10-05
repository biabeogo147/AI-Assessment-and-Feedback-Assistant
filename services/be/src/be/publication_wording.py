"""Hai câu luật về thời gian, viết đúng một lần — và viết **kèm số thật**.

ADR-03 dành cả một tài liệu để ngăn **đúng một** hiểu nhầm: giờ đóng là hạn **vào**, không
phải hạn **nộp**. Và nó ghi rõ hiểu nhầm đó gây hại theo chiều ngược — một giáo viên muốn
bài nộp xong trước 18:00 sẽ đặt giờ đóng 17:45 để bù, tức tự cắt mười lăm phút của cả lớp
mà không biết mình đang làm thế.

ADR-15 thì nói điều **ngược lại** cho pha 2: hạn kết thúc pha 2 là một mốc tuyệt đối, và
hết hạn thì cắt kể cả khi học sinh đang làm dở. Hai luật đối nhau trên cùng một biểu mẫu là
lý do cả hai phải được nói ra, chứ không phải chỉ một.

**Câu chữ ở đây sao đúng từng chữ từ Figma**, nơi ADR-03 đã chốt chúng ở ba chỗ:
`Publish settings` (`67:29`), `Consequence dialog` (`68:15`), và thẻ `đã-phát-hành` của
`Action result card`. Viết lại bằng lời khác ở BE sẽ là **cách diễn đạt thứ tư** cho cùng
một luật, đúng thứ mà ADR-03 gọi là ba luật — nên chỗ này không phát minh câu mới, nó chỉ
là nơi câu ấy sống trong code.

Và chúng là **hàm**, không phải hằng số, vì ADR-02 đòi hộp xác nhận *"đọc lại đúng giá trị
vừa nhập, không dùng con số ghi cứng"*. Câu của Figma có 18:00 và 18:15 trong đó, và 18:15
là một **phép tính** — giờ đóng cộng thời gian làm bài — tức chính con số diễn đạt ra cái
luật. Một câu chung chung không có số thì nói đúng mà không dạy được gì.

**Và biểu mẫu điền được chỗ trống của chính câu ấy.** Bản trước gửi cho biểu mẫu một câu đã
dựng sẵn với `--:--`; biểu mẫu tải nó **một lần lúc mở**, nên nó đứng ngay dưới mấy ô nhập,
trông như sắp đổi theo con số vừa gõ, mà về cấu trúc thì không bao giờ đổi được. Một câu
luật nói sai số ngay cạnh chỗ gõ số tệ hơn hẳn một câu luật vắng mặt.

Nên câu ấy nay sống dưới dạng **khuôn**: `PHASE_ONE` và `PHASE_TWO` ở dưới là nguồn duy
nhất, hàm dựng câu thật điền vào chính khuôn ấy, và biểu mẫu nhận đúng khuôn ấy qua API
rồi điền số đang gõ. Chữ nghĩa vì thế vẫn có **một** nơi — đổi một chữ ở đây là đổi ở cả
bốn chỗ.

**Và bốn thứ nhỏ hơn thì có hai bản**, nên hãy đọc rõ chúng ra thay vì hứa suông: phép cộng
*giờ đóng + phút làm bài*; tên bốn chỗ trống; `--:--`; và `--`. Ba thứ sau là **hợp đồng**
giữa file này và `PublishSettings.tsx`, không phải chuyện nội bộ — đổi một cái ở đây mà
không đổi bên kia thì biểu mẫu in ra `{last}` nguyên văn, hoặc hai bề mặt hiện hai kiểu chỗ
trống. `check_the_form_fills_the_slots_the_wording_declares` trong `tools/check_contract.py` là
nơi thi hành: nó đọc khuôn ở đây, đọc chỗ điền ở FE, và đỏ khi hai bên lệch. Phép cộng thì
được ghim bằng một test ở `test_publishing.py` và ba test ở FE.
"""

from datetime import datetime, timedelta

# Chỗ trống, cho lúc biểu mẫu chưa có giờ nào. Dùng một chuỗi thay vì bỏ cả câu đi, vì
# ADR-03 đòi câu ấy có mặt **lúc đang chọn giờ** -- đó là nơi thứ nhất trong ba nơi, và nó
# là nơi quan trọng nhất: một giáo viên đọc luật *trước* khi gõ thì không đặt giờ đóng
# 17:45 để bù.
_BLANK = "--:--"

# Chỗ trống cho một **con số**, không phải một mốc giờ. Dùng nhầm `--:--` ở đây thì khuôn
# câu của biểu mẫu lệch khuôn của hai payload kia, và đó đúng là thứ phép so khuôn trong
# test bắt được.
_BLANK_RATE = "--"

# Hai khuôn câu — **nguồn duy nhất** của chữ nghĩa này.
#
# Hàm ở dưới điền vào chính chúng, và biểu mẫu nhận đúng chúng qua API rồi điền con số
# đang gõ. Nhờ thế đổi một chữ ở đây là đổi ở cả bốn chỗ ADR-03 đòi phải giống nhau; và
# không chỗ nào còn hiện một câu luật nói sai số ngay cạnh ô nhập số ấy.
PHASE_ONE = "Vào tham gia tới hết {closes} - có thể nộp lúc {last}, và không dừng người đang làm."
PHASE_TWO = (
    "Chữa bài tới hết {deadline} - mỗi lượt {rate} phút một câu, và hết hạn thì lượt đang "
    "làm bị DỪNG."
)

# Ba lý do một bộ sáu tham số không dùng được.
#
# **Chúng là lời của BE, và biểu mẫu mượn đúng lời ấy để nói TRƯỚC cú bấm.** Trước đợt này
# chúng là ba string literal nằm trong `_schedule_fault`, và biểu mẫu không biết tới chúng:
# giáo viên điền mở 20:00 / đóng 08:00, nút vẫn sáng, và câu luật ngay dưới đó in ra *"Vào
# tham gia tới hết 08:00 - có thể nộp lúc 08:15"* bằng giọng khẳng định. Cổng BE chặn đúng,
# nên không ai phát hành được một cửa sổ vô lý -- nhưng câu luật là thứ duy nhất giáo viên
# đọc, và nó không bao giờ nói "bất khả thi".
#
# Cùng một lý lẽ với `PHASE_ONE` và `PHASE_TWO`: viết lại bằng lời khác ở FE là cách diễn
# đạt thứ hai cho một luật, và hai cách diễn đạt cho một luật là hai luật. ADR-03 đòi mọi
# nơi nói giống hệt nhau, và một lời từ chối cũng là một nơi nói ra luật ấy.
FAULT_OPENS_IN_THE_PAST = "giờ mở phải ở tương lai"
FAULT_CLOSES_BEFORE_OPENS = "giờ đóng phải sau giờ mở"
FAULT_PHASE_TWO_TOO_EARLY = "hạn pha 2 phải sau giờ nộp cuối của pha 1"

# Cửa sổ thu hồi (ADR-02). Không có số nào để điền: nó nói về giờ mở, mà giờ mở đã được
# nêu ra riêng dưới dạng `withdrawable_until`.
RECALL_RULE = (
    "Thu hồi được cho tới hết giờ mở. Sau giờ mở, khi học sinh đã có thể vào làm, phát "
    "hành không lấy lại được nữa."
)


def _clock(moment: datetime | None) -> str:
    """Một mốc thời gian theo cách giáo viên đọc nó, hoặc một chỗ trống.

    Chỉ giờ và phút, đúng như câu trên Figma: ngày đã nằm ở chỗ khác trên biểu mẫu, và
    một câu luật dài thêm mười ký tự ngày tháng là một câu ít ai đọc hết.

    Args:
        moment: Mốc cần viết ra, hoặc None khi biểu mẫu chưa có giờ nào.

    Returns:
        Dạng `HH:MM`, hoặc `--:--`.
    """
    return _BLANK if moment is None else moment.strftime("%H:%M")


def phase_one_note(closes_at: datetime | None = None, phase1_minutes: int | None = None) -> str:
    """Luật của pha 1, kèm hai con số thật của lớp này.

    Con số thứ hai là một **phép tính**: giờ đóng cộng thời gian làm bài, tức giờ mà bài
    cuối cùng còn có thể nộp. Đó chính là con số diễn đạt ra luật — "đóng 18:00, làm 15
    phút, thì bài cuối nộp 18:15" là ví dụ mà ADR-03 dùng — nên nó phải được BE tính, một
    lần, không phải mỗi màn hình tự tính một lần.

    Không tham số thì cùng câu ấy in ra với `--:--` ở cả hai chỗ số. Đó là **cùng một
    câu**, không phải một câu khác -- bản trước có một hằng số nói chung chung cho biểu
    mẫu, và nó là cách diễn đạt thứ tư cho đúng cái luật mà ADR-03 dành cả tài liệu để giữ
    cho chỉ có một.

    Args:
        closes_at: Hạn **vào** của lớp này, hoặc None khi chưa ai gõ giờ nào.
        phase1_minutes: Thời gian làm bài tính từ lúc học sinh vào, hoặc None.

    Returns:
        Câu luật của pha 1, đúng khuôn trên Figma.
    """
    last_submission = (
        None
        if closes_at is None or phase1_minutes is None
        else closes_at + timedelta(minutes=phase1_minutes)
    )
    return PHASE_ONE.format(closes=_clock(closes_at), last=_clock(last_submission))


def phase_two_note(
    remediation_deadline: datetime | None = None, minutes_per_question: int | None = None
) -> str:
    """Luật của pha 2, kèm hai con số thật của lớp này.

    Chữ **DỪNG** viết hoa, sao đúng từ Figma, và lý do nó viết hoa đáng giữ lại: đó là
    phần duy nhất của câu nói về một thứ học sinh **sắp mất**. Pha 1 không dừng ai giữa
    chừng, pha 2 thì dừng — hai luật đối nhau, và chữ viết hoa là chỗ sự đối nhau ấy nhìn
    thấy được.

    Args:
        remediation_deadline: Mốc tuyệt đối kết thúc pha 2.
        minutes_per_question: Một **tỉ lệ**, không phải một khoảng (ADR-15).

    Returns:
        Câu luật của pha 2, đúng khuôn trên Figma.
    """
    rate = _BLANK_RATE if minutes_per_question is None else str(minutes_per_question)
    return PHASE_TWO.format(deadline=_clock(remediation_deadline), rate=rate)
