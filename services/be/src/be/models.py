"""Hình dạng quan hệ của mọi thứ BE ghi nhớ.

ADR-21 làm state của Attempt trở nên bền: hạn của pha 2 còn cách hàng giờ hoặc
hàng ngày nữa, nên không gì trong file này được phép sống trong một cache có tuổi
thọ một giờ. AGENT không giữ credential nào của database này và sẽ không bao giờ
giữ -- một job chở theo đúng những gì nó cần.

Có hai lối tắt cố ý và được ghi rõ. Identifier là string UUID chứ không phải một
kiểu native, nhờ vậy cùng một bộ model chạy được trên Postgres khi phát triển và
trên SQLite khi test, không cần nhánh riêng theo dialect. Câu hỏi mà một round
sinh ra được lưu dạng JSON trên round item chứ không nằm trong các bảng question,
vì nó thuộc về đúng một round và không bao giờ bị so sánh giữa các dòng -- nâng
nó lên thành bảng riêng sẽ có nghĩa là phải chở một loại question thứ hai đi qua
mọi query đang đọc những câu do giáo viên soạn.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    """Đúc một identifier.

    Returns:
        Một UUID4 ở dạng string có dấu gạch nối.
    """
    return str(uuid.uuid4())


def aware(value: datetime) -> datetime:
    """Gắn UTC vào một datetime đọc từ database nếu nó về mà không có timezone.

    Mọi cột thời gian ở đây khai `DateTime(timezone=True)` và mọi giá trị ghi vào đều
    tz-aware, nhưng SQLite không có kiểu datetime nên nó trả về chuỗi đã mất phần
    offset. So một giá trị naive với `datetime.now(UTC)` thì `TypeError`, và nó nổ ở
    tầng route chứ không ở chỗ gây ra.

    Để ở `models` vì đây là chuyện đọc một **cột** về cho đúng, không phải chuyện luật
    nghiệp vụ -- và vì cả đường học sinh lẫn đường giáo viên đều cần nó. Hai bản của
    cùng một phép chuẩn hoá là thứ repo này đã trả giá một lần.

    Args:
        value: Giá trị đọc từ một cột datetime.

    Returns:
        Chính nó khi đã có timezone, hoặc một bản gắn UTC.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Base khai báo cho mọi bảng mà BE sở hữu."""


class AssessmentState(StrEnum):
    """Bốn state của ADR-01, theo thứ tự một đề đi qua chúng.

    Bộ từ vựng nằm ở đây vì nó là một phần của schema; còn các cạnh nối giữa
    những state này nằm trong `be/assessment_state.py`, module duy nhất được phép
    đưa một đề từ state này sang state khác.

    `PUBLISHED` giữ đúng cách viết mà seed đã ghi từ trước, nên những dòng tạo ra
    trước khi enum này tồn tại vẫn đọc lại y nguyên.

    ADR-02 chia state cuối thành hai sub-state -- đã phát hành nhưng chưa mở, và
    đã mở -- vì chỉ ở state đầu mới được phép withdraw. Phép chia đó được suy ra
    từ `Publication.opens_at` chứ không lưu thành thành viên thứ năm: một sự thật
    nằm ở hai nơi là hai sự thật, và tuần sau chúng sẽ lệch nhau.
    """

    EMPTY = "empty"
    HAS_QUESTIONS = "has_questions"
    APPROVED = "approved"
    PUBLISHED = "published"


class SchoolClass(Base):
    """Một lớp do giáo viên tạo, chứa học sinh của một danh sách lớp.

    `name` cố ý **không** unique. Hai giáo viên đều có thể có một lớp "12A", và
    một giáo viên có thể dùng lại một cái tên qua nhiều năm. Hệ quả là tên không
    phải identifier: việc phân giải thứ giáo viên gõ ra thành một trong những dòng
    này có thể trả về nhiều hơn một đáp án, và người gọi phải hỏi lại chứ không
    được lấy cái đầu tiên (cổng kiểm input của ADR-05).
    """

    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(64))

    teacher: Mapped[Teacher] = relationship(back_populates="classes")
    students: Mapped[list[Student]] = relationship(back_populates="school_class")


class Student(Base):
    """Một tài khoản học sinh, mà người thật tra theo mã học sinh của em."""

    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    full_name: Mapped[str] = mapped_column(String(128))
    student_code: Mapped[str] = mapped_column(String(32), unique=True)

    school_class: Mapped[SchoolClass] = relationship(back_populates="students")


class Teacher(Base):
    """Một tài khoản giáo viên."""

    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(128))
    teacher_code: Mapped[str] = mapped_column(String(32), unique=True)

    classes: Mapped[list[SchoolClass]] = relationship(back_populates="teacher")
    assessments: Mapped[list[Assessment]] = relationship(back_populates="teacher")


class Assessment(Base):
    """Một đề đi qua vòng đời của nó.

    `state` là vòng đời của ADR-01 và có **bốn** giá trị, không phải ba: một đề
    còn chưa có câu hỏi nào là một state riêng, vì chính state đó là thứ chặn việc
    phát hành. Duyệt khoá nội dung lại, và đó là lý do question không mang mốc
    thời gian sửa -- cái khoá là một state nằm trên dòng này, không phải một cờ
    riêng cho từng câu hỏi.

    `teacher_id` là người soạn. ADR-13 nói một lớp thuộc về một giáo viên, và điều
    tương tự cũng đúng với những gì giáo viên viết ra; trước khi có cột này, luật
    đó không có chỗ nào để sống, nên không query nào áp dụng được nó.
    """

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    title: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str] = mapped_column(String(16))
    # Ba tham số không để mặc định, mỗi cái vì một lý do riêng.
    #
    # `create_constraint` và `validate_strings` đều mặc định tắt, và những mặc
    # định đó là phương án tệ nhất trong ba: một string lạ được ghi xuống mà không
    # ai phàn nàn, rồi nó ném `LookupError` ở lần đọc bảng kế tiếp, trong bất kỳ
    # route nào tình cờ chạm vào nó sau đó. `validate_strings` đẩy lỗi về đúng
    # lần ghi đã gây ra nó; `create_constraint` đặt cùng luật đó vào schema, nên
    # một state ngoài ADR-01 cũng không lọt vào được qua psql.
    #
    # `values_callable` lưu *value* của thành viên enum. Không có nó, SQLAlchemy
    # lưu **tên** thành viên, nên cột sẽ chứa "PUBLISHED" trong khi ADR-01 và
    # `data-model.md` đều gọi là "published" -- và trong khi những dòng ghi trước
    # khi enum này tồn tại cũng đang chứa "published".
    state: Mapped[AssessmentState] = mapped_column(
        Enum(
            AssessmentState,
            native_enum=False,
            length=16,
            name="assessment_state",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=AssessmentState.EMPTY,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    teacher: Mapped[Teacher] = relationship(back_populates="assessments")
    questions: Mapped[list[Question]] = relationship(
        back_populates="assessment", order_by="Question.order_index"
    )
    # Một list, vì một đề được phát hành theo từng lớp. Chỗ này từng là
    # `uselist=False` khi một Publication là một dòng cho mỗi đề, và để nguyên như
    # vậy sẽ là một cái bẫy chứ không phải một thứ sót lại: với quan hệ một-một mà
    # tìm ra nhiều dòng, SQLAlchemy trả lời bằng một warning và *một dòng tuỳ ý*,
    # nên một người gọi sau này khi đi kiểm hạn thu hồi sẽ đọc được đúng cái lớp
    # mà nó tình cờ nhận.
    publications: Mapped[list[Publication]] = relationship(
        back_populates="assessment", order_by="Publication.opens_at"
    )


class Question(Base):
    """Một câu hỏi do giáo viên soạn, thuộc một đề."""

    __tablename__ = "questions"
    # Một câu cho mỗi vị trí trong một đề. `DraftItem` đã có constraint này từ Pha 2 và
    # bảng đích thì không, nên `harvest` chống trùng vị trí bằng một snapshot đọc vào bộ
    # nhớ -- và một snapshot thì không chặn được lần `harvest` thứ hai chạy song song với
    # nó. Pha 4 thêm một cửa thứ ba đi vào đó (endpoint duyệt cũng thu hoạch), nên đây là
    # lúc để database làm bên phân xử thay vì một biến cục bộ.
    __table_args__ = (UniqueConstraint("assessment_id", "order_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    learning_objective: Mapped[str] = mapped_column(String(160))

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    options: Mapped[list[AnswerOption]] = relationship(
        back_populates="question", order_by="AnswerOption.label"
    )
    methods: Mapped[list[Method]] = relationship(
        back_populates="question", order_by="Method.order_index"
    )


class AnswerOption(Base):
    """Một phương án của một câu hỏi, kèm lỗi sai mà nó đại diện.

    `error_label` là phần mapping Distractor do giáo viên soạn theo ADR-18, và nó
    null ở đúng một dòng trên mỗi câu hỏi: dòng của phương án đúng.
    """

    __tablename__ = "options"
    __table_args__ = (UniqueConstraint("question_id", "label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    label: Mapped[str] = mapped_column(String(4))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    error_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped[Question] = relationship(back_populates="options")


class Method(Base):
    """Một lời giải chi tiết của một câu hỏi. ADR-18 đòi phải có hơn một."""

    __tablename__ = "methods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)

    question: Mapped[Question] = relationship(back_populates="methods")


class Publication(Base):
    """Điều kiện phát hành một đề cho một lớp.

    Năm cột, không phải sáu: ADR-02 đòi **sáu** tham số lúc phát hành, nhưng tham số
    thứ nhất của nó là **lớp**, và ở đây lớp là nửa còn lại của khoá chính chứ không
    phải một cột cài đặt. Một hàng là một lớp đã chọn, cộng năm thứ giáo viên đặt cho
    lớp đó. `published_at` và `recalled_at` là sổ sách, không phải tham số.

    Một dòng cho mỗi **(đề, lớp)**. Phiên bản đầu của bảng này khoá theo đề mà
    thôi, kèm một docstring giải thích rằng hai bộ hạn cùng sống cho một đề là một
    trạng thái không ai giải thích nổi cho học sinh. Lập luận đó đã trộn lẫn một đề
    với một lớp, và nó sai theo một cách có hậu quả thật: 12A học bài đó vào buổi
    sáng nên cần mở vào buổi sáng, 12B học sau giờ trưa. Hai bộ điều kiện tự giải
    thích được hoàn hảo, vì một học sinh bao giờ cũng chỉ thấy bộ của chính mình.

    Phát hành lại cho *cùng* một lớp thì vẫn thay thế điều kiện của lớp đó chứ
    không thêm một bộ thứ hai -- vẫn là luật ban đầu, chỉ áp ở đúng cấp mà nó thực
    sự nói về.

    Thứ làm cho việc mở lệch giờ an toàn trước chuyện lớp này kể cho lớp kia lại là
    một tính năng khác: một đề rút câu hỏi của từng học sinh từ một bank lớn hơn
    (`docs/plans/backlog.md`). Chừng nào chưa có nó, mở lệch giờ chỉ là tiện lợi về
    xếp lịch, không phải một bảo đảm về bí mật.
    """

    __tablename__ = "publications"

    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"), primary_key=True)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase1_minutes: Mapped[int] = mapped_column(Integer)
    phase2_minutes_per_question: Mapped[int] = mapped_column(Integer)
    remediation_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped[Assessment] = relationship(back_populates="publications")


class Attempt(Base):
    """Một lượt làm của một học sinh trên một đề, trải qua cả hai pha.

    `submitted_at` kết thúc pha 1, không kết thúc Attempt (ADR-14). Attempt xong
    khi mọi câu sai đã đóng, hoặc khi hạn remediation đi qua.
    """

    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    # Lớp mà Attempt này được bắt đầu trong đó, chụp lại một lần. Giờ một đề có một
    # bộ điều kiện cho mỗi lớp, nên Attempt phải nói rõ bộ nào chi phối nó -- còn
    # nếu đọc lớp từ học sinh thay vì từ đây thì một lần chuyển lớp sẽ âm thầm thay
    # luôn các mốc hạn của phần việc đã làm xong.
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Answer(Base):
    """Thứ một học sinh đã chọn cho một câu hỏi của pha 1.

    Được lưu ở mỗi lần click chứ không phải lúc nộp, nên mất mạng là mất một lần
    click, không phải mất cả bài.
    """

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    option_id: Mapped[str] = mapped_column(ForeignKey("options.id"))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionOutcome(Base):
    """Phán quyết hiện hành trên một câu hỏi của một Attempt.

    Đây là sổ điểm. `mark` chỉ có thể tăng: pha 1 đặt mức sàn, còn remediation có
    thể nâng một 0 lên 0.5, chứ không bao giờ theo chiều ngược lại (ADR-16).
    `rounds_used` là bộ đếm theo từng câu hỏi mà ADR-17 chặn trần ở ba.
    """

    __tablename__ = "question_outcomes"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    mark: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(24))
    rounds_used: Mapped[int] = mapped_column(Integer, default=0)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)


class RemediationRound(Base):
    """Một round có đồng hồ, phủ mọi câu hỏi còn đang mở.

    Một round gom tất cả câu còn lại chứ không chỉ một câu, vì pha 2 nhận một đề,
    không nhận một câu hỏi (ADR-17).

    **Mỗi Attempt có nhiều nhất một round chưa nộp, và chính database là thứ ép
    điều đó.** Route có kiểm trước, nhưng một lần kiểm rồi một lần insert là hai
    câu lệnh: hai tab cùng bấm nút một lúc thì cả hai đều qua được lần kiểm và cả
    hai đều ghi. Khi đó học sinh giữ hai cái đồng hồ, điều mà ADR-15 không gán cho
    một ý nghĩa nào. Partial unique index bên dưới biến cuộc đua đó thành một lỗi
    toàn vẹn, rồi route chuyển nó thành một lời từ chối.
    """

    __tablename__ = "rounds"
    __table_args__ = (
        Index(
            "uq_one_open_round_per_attempt",
            "attempt_id",
            unique=True,
            postgresql_where=text("submitted_at IS NULL"),
            sqlite_where=text("submitted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    index: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[RoundItem]] = relationship(back_populates="round")


class RoundItem(Base):
    """Câu hỏi được sinh ra mà một round đặt ra cho một câu hỏi gốc.

    `options` và `methods` là JSON vì câu hỏi này thuộc về round này và không thuộc
    về gì khác. Việc giữ phương án đúng ngay ở đây, phía server, chính là thứ cho
    phép BE chấm round mà không phải hỏi AGENT bất cứ điều gì (ADR-20).
    """

    __tablename__ = "round_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id"))
    origin_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict]] = mapped_column(JSON)
    methods: Mapped[list[dict]] = mapped_column(JSON)
    chosen_label: Mapped[str | None] = mapped_column(String(4), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)

    round: Mapped[RemediationRound] = relationship(back_populates="items")


class PregeneratedItem(Base):
    """Câu hỏi của một round, được viết trước khi học sinh yêu cầu nó.

    Viết một câu hỏi tốn của model gần hai mươi giây, và làm việc đó vào lúc học
    sinh bấm nút có nghĩa là học sinh ngồi nhìn một màn hình trắng đúng bằng khoảng
    thời gian ấy. Nhưng ADR-14 đưa em qua màn hình kèm học trước, và đó là vài phút
    đọc và hỏi. Vậy nên việc được khởi động ngay khi pha 1 được nộp rồi mới thu lại
    sau: thời gian chờ được tiêu vào một việc mà học sinh tự chọn làm.

    **AGENT không ghi bảng này.** Nó không giữ credential nào của database và
    `tools/check_contract.py` giữ cho chuyện đó đúng như vậy, nên BE tự đọc job đã
    xong từ queue rồi tự lưu vào đây.

    `status` chạy `pending -> ready`, hoặc `pending -> failed` khi job đã chạy và
    ném lỗi. Còn một job mà kết quả chỉ đơn giản là hết hạn trong Redis -- chuyện
    bình thường, vì kết quả sống một giờ còn hạn pha 2 có thể cách đó nhiều ngày --
    thì dòng của nó bị **xoá** thay vì đánh dấu, nhờ vậy một luật duy nhất "một câu
    hỏi không có dòng cho round nó cần thì được đẩy một job vào queue" phủ được cả
    trường hợp chưa bao giờ bắt đầu và trường hợp đã bắt đầu nhưng mất kết quả.
    `failed` được giữ lại chính là để nó *không* bị đẩy lại vào queue: cùng một job
    sẽ gãy theo cùng một cách, mỗi lần học sinh mở một màn hình.

    Unique index ở đây không phải đồ trang trí. Hai tab trên màn hình kèm học cùng
    poll, cùng tìm thấy một job đã xong, và cùng insert; kiểm trước rồi ghi sau là
    hai câu lệnh với một khoảng trống ở giữa. Vẫn là bài học của
    `uq_one_open_round_per_attempt` ở trên, và học được theo cùng một cách.
    """

    __tablename__ = "pregenerated_items"
    __table_args__ = (
        Index(
            "uq_one_pregenerated_per_round",
            "attempt_id",
            "origin_question_id",
            "round_index",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    origin_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    round_index: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(8), default="pending")
    stem: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    methods: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    """Một lượt của cuộc hội thoại pha 2, được lưu trước khi stream ra.

    Thứ tự là theo `created_at` cộng với `sequence`, vì hai lượt có thể rơi vào cùng
    một nhịp đồng hồ, và một cuộc hội thoại tự sắp xếp lại thứ tự khi tải lại là một
    cuộc hội thoại khác.
    """

    __tablename__ = "chat_messages"
    # Một lượt cho mỗi vị trí. Hai request có thể cùng tới lượt mở đầu trong khi
    # cầm cùng một lịch sử rỗng -- StrictMode của React mở stream hai lần theo đúng
    # thiết kế -- và một lần kiểm rồi một lần insert là hai câu lệnh với một khoảng
    # trống ở giữa. Không có cái này thì học sinh được chào hai lần, bởi hai dòng mà
    # cả hai đều tự nhận là dòng đầu tiên.
    __table_args__ = (UniqueConstraint("attempt_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Report(Base):
    """Một học sinh nói rằng lời giải thích của trợ lý khó theo.

    Phạm vi là Attempt, không phải một message: trợ lý làm việc trên cả đề, nên một
    báo cáo chỉ vào đúng một lượt sẽ hứa với giáo viên một thứ hẹp hơn thực tế
    (ADR-19).
    """

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TeacherConversation(Base):
    """Một cuộc hội thoại đang chạy giữa một giáo viên và trợ lý.

    Là một bảng chứ không phải một id trơ trên từng lượt, để sau này giáo viên có
    thể mở một luồng mới mà những lượt cũ không đi theo vào đó. Chừng nào thứ đó
    chưa được làm, BE dùng lại cuộc hội thoại gần nhất.
    """

    __tablename__ = "teacher_conversations"
    # Một cái cho mỗi giáo viên, ở thời điểm này. Luật đó là thật -- BE dùng lại
    # cuộc hội thoại đang chạy và không cho cách nào mở cái khác -- nên nó thuộc về
    # schema, chứ không thuộc về niềm hy vọng rằng hai request không bao giờ tới
    # cùng lúc. Hai request của một giáo viên vẫn tới cùng lúc như thường: một màn
    # hình đang tải trong khi họ đang gõ.
    #
    # Ngày mà giáo viên mở được luồng thứ hai, constraint này được bỏ đi một cách có
    # chủ ý, và `_latest_conversation` vốn đã sắp theo một khoá thứ hai nên việc chọn
    # giữa các luồng vẫn xác định.
    __table_args__ = (UniqueConstraint("teacher_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    turns: Mapped[list[TeacherTurn]] = relationship(
        back_populates="conversation", order_by="TeacherTurn.sequence"
    )


class TeacherTurn(Base):
    """Một step trong lượt của giáo viên: điều gì đã được nói, hoặc điều gì đã chạy.

    Không phải một dòng của `chat_messages`, và lý do là cơ học chứ không phải chuyện
    khẩu vị: `attempt_id` của bảng đó là foreign key trỏ tới `attempts`, còn cuộc hội
    thoại của giáo viên thì không có Attempt nào.

    Điều nó giữ ngoài phần lời mới là trọng tâm. Một lượt của giáo viên có thể là "đã
    tạo đề nháp 10 câu cho 12A1", và thứ đáng lưu là *đề nháp nào*, không phải câu
    văn thông báo về nó -- nên `entity_kind` và `entity_id` chở theo cái chủ thể đó,
    và đó cũng là thứ cho phép giao diện chọn đúng biến thể `Action result card` sau
    một lần tải lại.

    `model_tokens` và `duration_ms` làm cho bảng này vừa là transcript vừa là trace.
    Một hệ thống tracing riêng sẽ là cùng những dòng đó được ghi hai lần, và với một
    agent tự chọn step của mình, "nó đã làm gì" là câu hỏi không trả lời được nếu
    thiếu hai cột này.
    """

    __tablename__ = "teacher_turns"
    # Một step cho mỗi vị trí, cố ý sao lại từ `chat_messages`. Bài học ở đó vẫn
    # đúng: StrictMode của React bắn một request hai lần theo đúng thiết kế, và một
    # lần kiểm rồi một lần insert là hai câu lệnh với một khoảng trống ở giữa.
    __table_args__ = (UniqueConstraint("conversation_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("teacher_conversations.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text, default="")
    tool_name: Mapped[str] = mapped_column(String(64), default="")
    tool_args: Mapped[dict] = mapped_column(JSON, default=dict)
    tool_result: Mapped[dict] = mapped_column(JSON, default=dict)
    # Step này nói về cái gì, trong trường hợp nó có nói về một cái gì. Một đề nháp,
    # một lớp, một đề -- đủ để liên kết tới nó và để chọn cách vẽ step ra.
    entity_kind: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(36), default="")
    model_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    conversation: Mapped[TeacherConversation] = relationship(back_populates="turns")


class DraftBrief(Base):
    """Thứ giáo viên đã yêu cầu, ghi xuống một lần trước khi câu hỏi nào được viết.

    Một dòng cho mỗi đề, và nó tồn tại để một bộ câu hỏi có thể nhất quán. Các câu
    hỏi được viết bởi những job độc lập không thấy được nhau, nên nếu phần chỉ dẫn
    vẫn có thể đổi trong lúc chúng đang chạy thì nửa đầu và nửa sau của một đề sẽ trả
    lời hai câu hỏi khác nhau -- và không ai đọc từng câu một sẽ nhận ra điều đó.

    Ra brief lại thì thay thế dòng này, và việc đó khởi động một vòng sinh câu **mới**.
    Vì thế "làm khó hơn đi" là một brief mới, không phải một thay đổi áp lên phần việc
    đang bay giữa đường.

    Môn và khối nằm trên `Assessment` và không được sao lại vào đây: một sự thật nằm ở
    hai nơi là hai sự thật, và tuần sau chúng sẽ lệch nhau.
    """

    __tablename__ = "draft_briefs"

    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    topic_scope: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(64), default="")
    question_count: Mapped[int] = mapped_column(Integer)
    # Tăng lên ở mỗi lần ra brief lại. Một câu hỏi viết cho một version trước đó bị
    # loại bỏ chứ không trộn vào, và chính điều đó làm cho "làm khó hơn đi" là một
    # vòng mới chứ không phải một lần sửa áp lên phần việc đang bay giữa đường -- còn
    # nếu không có nó, lời khẳng định rằng một bộ đề được viết dựa trên một cách hiểu
    # duy nhất về chủ đề chỉ là một niềm hy vọng, không phải một cơ chế.
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DraftItem(Base):
    """Một câu hỏi của một đề nháp, trong lúc nó còn đang được viết.

    Cùng hình dạng với `PregeneratedItem` ở phía học sinh, và vì cùng một lý do: model
    chậm và không ai nên phải ngồi chờ nó. Một dòng cho mỗi vị trí, một job cho mỗi
    dòng.

    `status` là một trong bốn giá trị:

    - `pending` -- một job đang chạy.
    - `ready` -- câu hỏi đã nằm trong đề nháp.
    - `retry` -- câu trả lời không dùng được theo kiểu do may rủi chứ không phải một
      lỗi cố định: một kết quả hết hạn trong Redis, hai job song song viết ra cùng một
      stem, một model đánh dấu hai phương án là đúng. Lần `fire` tiếp theo nhặt vị trí
      đó lên lại.
    - `failed` -- bỏ cuộc ở vị trí này. Hoặc chính job đã ném lỗi, hoặc `attempts` đã
      cạn.

    Chỗ tách `retry` khỏi `failed` là phần đáng giữ. Đánh mọi lần từ chối thành `failed`
    để lại một đề nháp thiếu câu mãi mãi mà không có cách nào bù vào; còn xoá mọi dòng
    bị từ chối thì lại đẩy vào queue, ở mọi lần đọc và mãi mãi, một câu hỏi mà model
    không thể viết đúng. `attempts` là thứ làm cho khoảng giữa trở nên khả thi.
    """

    __tablename__ = "draft_items"
    __table_args__ = (UniqueConstraint("assessment_id", "ordinal"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # Vị trí này đã tốn bao nhiêu job, để một model không viết nổi câu hỏi thì thôi
    # không bị hỏi nữa.
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    # Job này được bắn dưới brief nào. Một dòng thuộc brief cũ hơn sẽ bị loại bỏ lúc
    # harvest.
    brief_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
